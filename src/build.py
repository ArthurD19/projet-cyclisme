"""Pipeline complet : `python -m src.build` (les 7 coureurs d'un coup).

Écrit dans outputs/ :
- rides.parquet     une ligne par sortie
- daily.parquet     une ligne par coureur et par jour (charge + Hooper)
- mmp.parquet       records de puissance par coureur et par mois
- ride_mmp.parquet  records de puissance de chaque sortie (pour filtrer une période)
- ftp.parquet       FTP mensuelle par coureur
- traces.parquet    traces allégées (1 point / 20 s) pour l'explorateur de séance
- riders.parquet    fiche synthétique par coureur
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import load, metrics, profile, tracking
from .config import HR_REST_DEFAULT_BPM, HR_REST_FILE_OWNER, MMP_DURATIONS_S, OUTPUTS, list_cyclists


def _summ(args):
    path, cid, kg = args
    try:
        return metrics.summarize_ride(path, cid, kg)
    except Exception as e:  # une sortie illisible ne bloque pas le pipeline
        print(f"  ! {path.name}: {e}", file=sys.stderr)
        return None


def season_hr_max(r: pd.DataFrame) -> pd.Series:
    """FCmax par saison = max des sorties, en écartant un pic isolé (artefact capteur)."""
    def robust_max(s):
        s = s.dropna().sort_values(ascending=False)
        if s.empty:
            return np.nan
        ref = s.iloc[:10].median()
        return float(s[s <= ref + 8].max())
    return r.groupby(r["date"].dt.year)["hr_max_bpm"].apply(robust_max)


def build() -> None:
    t0 = time.time()
    OUTPUTS.mkdir(exist_ok=True)
    cyclists = list_cyclists()
    hr_rest_c4 = load.read_hr_rest()

    rides_all, daily_all, mmp_rows, traces, ftp_all, riders = [], [], [], [], [], []
    for c in cyclists:
        files = load.list_ride_files(c)
        print(f"{c.label} ({c.weight_kg:.0f} kg) : {len(files)} sorties…", flush=True)
        with ProcessPoolExecutor() as ex:
            res = [x for x in ex.map(_summ, [(f, c.id, c.weight_kg) for f in files], chunksize=8) if x]

        r = pd.DataFrame([x["rec"] for x in res])
        mm = pd.DataFrame([x["mmp"] for x in res], columns=MMP_DURATIONS_S)
        mm["file"], mm["date"], mm["cyclist"] = r["file"].values, r["date"].values, c.id
        mm = mm.melt(id_vars=["cyclist", "file", "date"], var_name="dur_s", value_name="p_w")
        mm["dur_s"] = mm["dur_s"].astype(int)
        mm["p_wkg"] = mm["p_w"] / c.weight_kg

        # Seuils du coureur
        ftp = profile.monthly_ftp(mm)
        ftp["cyclist"] = c.id
        ftp_map = dict(zip(ftp["month"], ftp["ftp_w"]))
        hrmax = season_hr_max(r)
        hr_rest_default = float(hr_rest_c4.median()) if c.id == HR_REST_FILE_OWNER else HR_REST_DEFAULT_BPM

        extra = []
        for x, (_, row) in zip(res, r.iterrows()):
            f = ftp_map.get(row["date"].to_period("M"), np.nan)
            hm = hrmax.get(row["date"].year, np.nan)
            hrr = hr_rest_c4.get(row["date"], hr_rest_default) if c.id == HR_REST_FILE_OWNER else hr_rest_default
            extra.append(metrics.apply_thresholds(x["rec"], x["p_hist"], x["h_hist"], f, hm, hrr))
        r = pd.concat([r, pd.DataFrame(extra)], axis=1)
        r["ftp_wkg"] = r["ftp_w"] / c.weight_kg

        # RPE / lactate (jointure sur le nom du fichier)
        seances, hooper = load.read_psy(c)
        r = r.merge(seances, left_on="file", right_on="fichier", how="left").drop(columns="fichier")
        r["srpe"] = r["rpe"] * r["dur_s"] / 60
        r.loc[r["artifact"], ["srpe", "tss", "trimp_banister", "trimp_edwards"]] = np.nan

        # Charge unifiée (échelle TSS) : puissance si dispo, sinon FC, sinon ressenti
        both = r["has_power"] & r["trimp_banister"].gt(0) & r["tss"].gt(0)
        k_hr = float((r.loc[both, "tss"] / r.loc[both, "trimp_banister"]).median())
        both_s = r["has_power"] & r["srpe"].gt(0) & r["tss"].gt(0)
        k_rpe = float((r.loc[both_s, "tss"] / r.loc[both_s, "srpe"]).median())
        r["load"] = r["tss"]
        r["load_source"] = np.where(r["has_power"], "puissance", None)
        m = r["load"].isna() & r["trimp_banister"].notna()
        r.loc[m, "load"] = r.loc[m, "trimp_banister"] * k_hr
        r.loc[m, "load_source"] = "FC (estimée)"
        m = r["load"].isna() & r["srpe"].notna()
        r.loc[m, "load"] = r.loc[m, "srpe"] * k_rpe
        r.loc[m, "load_source"] = "RPE (estimée)"
        r["load_source"] = r["load_source"].fillna("aucune")
        r.loc[r["artifact"], ["load", "load_source"]] = [np.nan, "artefact écarté"]

        d = tracking.build_daily(r[~r["artifact"]], hooper, c.id)

        # Records mensuels
        mm["month"] = mm["date"].dt.to_period("M").dt.to_timestamp()
        mo = mm.dropna(subset=["p_w"]).sort_values("p_w").groupby(["cyclist", "month", "dur_s"]).tail(1)

        curve = profile.record_curve(mm)
        cp = profile.fit_cp(curve)
        scores = profile.profile_scores(curve, c.weight_kg)
        pheno, pheno_txt = profile.phenotype(scores)
        riders.append(dict(
            cyclist=c.id, num=c.num, label=c.label, weight_kg=c.weight_kg,
            first_date=r["date"].min(), last_date=r["date"].max(),
            seasons=", ".join(str(y) for y in sorted(r["date"].dt.year.unique())),
            n_rides=int((~r["artifact"]).sum()), n_artifacts=int(r["artifact"].sum()), hours=r.loc[~r["artifact"], "dur_s"].sum() / 3600,
            km=r.loc[~r["artifact"], "dist_km"].sum(),
            share_power=r["has_power"].mean(), share_hr=r["has_hr"].mean(), share_indoor=r["indoor"].mean(),
            ftp_w_last=float(ftp["ftp_w"].iloc[-1]), ftp_w_max=float(ftp["ftp_w"].max()),
            cp_w=cp["cp_w"], wprime_j=cp["wprime_j"], cp_r2=cp["r2"],
            hr_max_bpm=float(hrmax.max()), hr_rest_bpm=hr_rest_default,
            hr_rest_measured=c.id == HR_REST_FILE_OWNER,
            k_tss_per_trimp=k_hr, k_tss_per_srpe=k_rpe,
            compliance_rpe=r["rpe"].notna().mean(), compliance_lactate=r["lactate_mmol"].notna().mean(),
            compliance_hooper=d["hooper_filled"].mean(),
            phenotype=pheno, phenotype_txt=pheno_txt,
            **{f"score_{int(s.dur_s)}": s.score for s in scores.itertuples()},
            **{f"wkg_{int(s.dur_s)}": s.wkg for s in scores.itertuples()},
        ))

        rides_all.append(r); daily_all.append(d); mmp_rows.append((mm, mo)); ftp_all.append(ftp)
        traces.append(pd.concat([x["trace"] for x in res], ignore_index=True))
        print(f"   FTP {ftp['ftp_w'].iloc[-1]:.0f} W · CP {cp['cp_w']:.0f} W · FCmax {hrmax.max():.0f} · {pheno}"
              f" · charge sans puissance : {(r['load_source'] != 'puissance').sum()} sorties", flush=True)

    rides = pd.concat(rides_all, ignore_index=True)
    daily = pd.concat(daily_all, ignore_index=True)
    ride_mmp = pd.concat([a for a, _ in mmp_rows], ignore_index=True).drop(columns="month")
    mmp = pd.concat([b for _, b in mmp_rows], ignore_index=True).rename(columns={"file": "record_file"})
    ftp = pd.concat(ftp_all, ignore_index=True)
    ftp["month"] = ftp["month"].dt.to_timestamp()
    tr = pd.concat(traces, ignore_index=True)

    rides.to_parquet(OUTPUTS / "rides.parquet", index=False)
    daily.to_parquet(OUTPUTS / "daily.parquet", index=False)
    mmp.to_parquet(OUTPUTS / "mmp.parquet", index=False)
    ride_mmp.dropna(subset=["p_w"]).to_parquet(OUTPUTS / "ride_mmp.parquet", index=False)
    ftp.to_parquet(OUTPUTS / "ftp.parquet", index=False)
    tr.to_parquet(OUTPUTS / "traces.parquet", index=False, compression="zstd")
    pd.DataFrame(riders).to_parquet(OUTPUTS / "riders.parquet", index=False)
    print(f"OK : {len(rides)} sorties, {len(daily)} jours-coureur en {time.time() - t0:.0f} s → {OUTPUTS}")


if __name__ == "__main__":
    build()
