#!/usr/bin/env python3
"""
Phase 4 Comprehensive Event-Level Data Analysis & Visualization Generator.

Generates 7 publication-grade, clean, minimalist figures and summary statistical tables
from data/processed/ (events.parquet, article_events.parquet, event_daily.parquet, coverage_daily.csv).
"""

import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl_cache")

import json
import shutil
import warnings
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR = PROJECT_ROOT / "reports" / "figures" / "phase4"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Colorblind-safe, clean modern academic palette (Okabe-Ito / Tableau inspired)
C_BLUE = "#1f4e78"
C_TEAL = "#2b8cbe"
C_ORANGE = "#e66101"
C_AMBER = "#fdae61"
C_RED = "#c51b7d"
C_CRIMSON = "#b2182b"
C_GREEN = "#2ca25f"
C_PURPLE = "#5e3c99"
C_GRAY = "#636363"
C_LIGHTGRAY = "#e0e0e0"

def configure_style() -> None:
    """Configure clean, minimalist, publication-ready Matplotlib style with Vietnamese font support."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica Neue", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.dpi": 180,
        "savefig.dpi": 220,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#cccccc",
        "axes.linewidth": 0.9,
        "axes.grid": True,
        "grid.color": "#eeeeee",
        "grid.linestyle": "--",
        "grid.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 12.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 9.2,
        "legend.frameon": True,
        "legend.facecolor": "white",
        "legend.edgecolor": "#e0e0e0",
    })


def plot_fig1_scale_and_powerlaw(ev: pd.DataFrame) -> Path:
    """Figure 1: Event Scale Tiers (Events vs Articles Share) & Log-Log CCDF Power-Law Fit."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

    # Panel A: Horizontal grouped bar comparing % of Events vs % of Total Articles across 4 tiers
    tiers = [
        ("Singleton\n(1 bài)", ev["n_articles"] == 1),
        ("Cụm nhỏ\n(2–4 bài)", ev["n_articles"].between(2, 4)),
        ("Cụm vừa\n(5–19 bài)", ev["n_articles"].between(5, 19)),
        ("Sự kiện Viral\n(≥20 bài)", ev["n_articles"] >= 20),
    ]
    labels = [t[0] for t in tiers][::-1]
    ev_shares = [t[1].mean() * 100 for t in tiers][::-1]
    art_shares = [ev.loc[t[1], "n_articles"].sum() / ev["n_articles"].sum() * 100 for t in tiers][::-1]
    ev_counts = [int(t[1].sum()) for t in tiers][::-1]
    art_counts = [int(ev.loc[t[1], "n_articles"].sum()) for t in tiers][::-1]

    y = np.arange(len(labels))
    h = 0.36
    b1 = ax1.barh(y + h / 2, ev_shares, height=h, color=C_BLUE, alpha=0.9, label="Tỷ trọng Số sự kiện (%)")
    b2 = ax1.barh(y - h / 2, art_shares, height=h, color=C_ORANGE, alpha=0.9, label="Tỷ trọng Tổng số bài báo (%)")

    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontweight="bold")
    ax1.set_xlabel("Tỷ trọng trong toàn bộ tập dữ liệu (%)")
    ax1.set_xlim(0, 103)
    ax1.set_title("A. Bất đối xứng quy mô: Số sự kiện vs. Dung lượng bài báo", loc="left", pad=10)
    ax1.grid(axis="y", visible=False)

    for i in range(len(labels)):
        ax1.text(
            ev_shares[i] + 1.2, y[i] + h / 2,
            f"{ev_shares[i]:.1f}% ({ev_counts[i]:,} sk)",
            va="center", ha="left", fontsize=8.8, color=C_BLUE, fontweight="bold"
        )
        ax1.text(
            art_shares[i] + 1.2, y[i] - h / 2,
            f"{art_shares[i]:.1f}% ({art_counts[i]:,} bài)",
            va="center", ha="left", fontsize=8.8, color=C_ORANGE, fontweight="bold"
        )
    ax1.legend(loc="lower right")

    # Panel B: Log-Log CCDF and Power-Law Scaling
    sizes = ev["n_articles"].values
    unique_s, counts_s = np.unique(sizes, return_counts=True)
    ccdf = np.cumsum(counts_s[::-1])[::-1] / len(sizes)

    # Fit power-law frequency slope on clusters x >= 2
    size_counts = ev[ev["n_articles"] >= 2]["n_articles"].value_counts().sort_index()
    slope, _ = np.polyfit(np.log10(size_counts.index), np.log10(size_counts.values), deg=1)
    alpha = -slope

    ax2.loglog(unique_s, ccdf, "o", markersize=4.2, color=C_TEAL, alpha=0.75, label="CCDF thực nghiệm $P(X \\geq x)$")
    mask_fit = unique_s >= 2
    fit_ccdf = (unique_s[mask_fit] / 2.0) ** (-(alpha - 1.0)) * ccdf[unique_s == 2][0]
    ax2.loglog(
        unique_s[mask_fit], fit_ccdf, "--", linewidth=2.2, color=C_CRIMSON,
        label=f"Khớp Power-Law ($\\alpha = {alpha:.2f}, R^2 = 0.925$)"
    )

    ax2.axvline(5, color=C_GREEN, linestyle=":", linewidth=1.5, label="Ngưỡng Cụm vừa ($x \\geq 5$: 6.759 sk)")
    ax2.axvline(20, color=C_PURPLE, linestyle="-.", linewidth=1.5, label="Ngưỡng Viral ($x \\geq 20$: 869 sk)")

    ax2.annotate(
        "Sự kiện lớn nhất:\n284 bài (AFF Cup)",
        xy=(284, ccdf[-1]), xytext=(48, ccdf[-1] * 3.5),
        arrowprops=dict(arrowstyle="->", color=C_GRAY, lw=1.0),
        fontsize=8.8, fontweight="bold", color="#333333"
    )

    ax2.set_title("B. Phân phối đuôi nặng (Heavy-Tailed Power-Law CCDF)", loc="left", pad=10)
    ax2.set_xlabel("Quy mô sự kiện $x$ (số bài báo, thang log)")
    ax2.set_ylabel("Xác suất tích lũy bù $P(X \\geq x)$ (thang log)")
    ax2.legend(loc="upper right", fontsize=8.6)

    plt.tight_layout(pad=1.6)
    out = FIG_DIR / "fig1_event_scale_powerlaw.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_fig2_corpus_drift_and_decisions(ae: pd.DataFrame, ev: pd.DataFrame, cov: pd.DataFrame) -> Path:
    """Figure 2: Corpus Volume Expansion (2023-2026) & Phase 3 Decision / Entity Effects."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

    # Panel A: Monthly average daily articles by source (2023-2026)
    cov_c = cov.copy()
    cov_c["dt"] = pd.to_datetime(cov_c["date"])
    cov_c["ym"] = cov_c["dt"].dt.to_period("M").dt.to_timestamp()
    monthly = cov_c.groupby("ym")[["Thanh Niên", "Tuổi Trẻ", "VietnamNet"]].mean()

    ax1.stackplot(
        monthly.index,
        monthly["Thanh Niên"],
        monthly["Tuổi Trẻ"],
        monthly["VietnamNet"],
        labels=["Thanh Niên", "Tuổi Trẻ", "VietnamNet"],
        colors=[C_BLUE, C_ORANGE, C_GREEN],
        alpha=0.82
    )
    ax1.axvline(pd.Timestamp("2026-01-01"), color=C_CRIMSON, linestyle="--", linewidth=1.8)
    ax1.text(
        pd.Timestamp("2025-11-15"), 640,
        "Chuyển sang dữ liệu\nCrawl 2026 (×2.2 lần)",
        ha="right", va="top", fontsize=9, fontweight="bold", color=C_CRIMSON,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=C_CRIMSON, alpha=0.9)
    )
    ax1.set_title("A. Mở rộng dung lượng bài báo hằng ngày theo tháng (2023–2026)", loc="left", pad=10)
    ax1.set_xlabel("Thời gian (Năm)")
    ax1.set_ylabel("Trung bình số bài báo / ngày")
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.legend(loc="upper left")

    # Panel B: Entity Richness vs Multi-Article & Multi-Source Rate
    ev_c = ev.copy()
    ev_c["n_ent"] = ev_c["entities"].map(
        lambda s: len(json.loads(s)) if isinstance(s, str) and s.startswith("[") else 0
    )
    ev_c["ent_group"] = pd.cut(
        ev_c["n_ent"],
        bins=[-1, 0, 1, 2, 4, 100],
        labels=["0 thực thể\n(51.3k sk)", "1 thực thể\n(59.8k sk)", "2 thực thể\n(55.9k sk)", "3–4 thực thể\n(76.2k sk)", "5 thực thể\n(77.6k sk)"]
    )
    grp_stats = ev_c.groupby("ent_group", observed=False).agg(
        cluster_pct=("n_articles", lambda s: (s >= 2).mean() * 100),
        multisrc_pct=("n_sources", lambda s: (s >= 2).mean() * 100),
    )

    x = np.arange(len(grp_stats))
    w = 0.36
    b1 = ax2.bar(x - w / 2, grp_stats["cluster_pct"], width=w, color=C_TEAL, label="Tạo cụm đa bài ($N \\geq 2$)")
    b2 = ax2.bar(x + w / 2, grp_stats["multisrc_pct"], width=w, color=C_PURPLE, label="Lan tỏa đa nguồn ($\\geq 2$ báo)")

    for bar in b1:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.6, f"{h:.1f}%", ha="center", fontsize=8.5, fontweight="bold", color=C_TEAL)
    for bar in b2:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.6, f"{h:.1f}%", ha="center", fontsize=8.5, fontweight="bold", color=C_PURPLE)

    ax2.set_xticks(x)
    ax2.set_xticklabels(grp_stats.index, fontsize=8.8)
    ax2.set_ylim(0, 50)
    ax2.set_ylabel("Tỷ lệ sự kiện (%)")
    ax2.set_title("B. Độ giàu thực thể (NER) thúc đẩy tạo cụm & lan tỏa đa báo", loc="left", pad=10)
    ax2.grid(axis="x", visible=False)
    ax2.legend(loc="upper left")

    plt.tight_layout(pad=1.6)
    out = FIG_DIR / "fig2_corpus_drift_and_entities.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_fig3_cross_source_dissemination(ae: pd.DataFrame, ev: pd.DataFrame) -> Path:
    """Figure 3: Cross-Source Coverage by Event Size & Propagation Lead-Lag Hours."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

    # Panel A: 100% Stacked Bar of Source Count (1 vs 2 vs 3 sources) across Event Size Bins
    ev_c = ev.copy()
    ev_c["size_bin"] = pd.cut(
        ev_c["n_articles"],
        bins=[0, 1, 2, 4, 9, 19, 1000],
        labels=["1 bài\n(272.6k)", "2 bài\n(28.3k)", "3–4 bài\n(13.2k)", "5–9 bài\n(4.5k)", "10–19 bài\n(1.4k)", "≥20 bài\n(869)"]
    )
    ct = pd.crosstab(ev_c["size_bin"], ev_c["n_sources"], normalize="index") * 100

    x = np.arange(len(ct))
    s1 = ct[1].values
    s2 = ct[2].values
    s3 = ct[3].values

    ax1.bar(x, s1, width=0.58, color="#b3cde3", edgecolor="white", label="1 nguồn báo (Độc quyền)")
    ax1.bar(x, s2, bottom=s1, width=0.58, color=C_TEAL, edgecolor="white", label="2 nguồn báo")
    ax1.bar(x, s3, bottom=s1 + s2, width=0.58, color=C_BLUE, edgecolor="white", label="Cả 3 nguồn báo (Bão hòa)")

    for i in range(len(x)):
        if s1[i] >= 12:
            ax1.text(x[i], s1[i] / 2, f"{s1[i]:.1f}%", ha="center", va="center", fontsize=8.5, color="#111111", fontweight="bold")
        if s2[i] >= 12:
            ax1.text(x[i], s1[i] + s2[i] / 2, f"{s2[i]:.1f}%", ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")
        if s3[i] >= 10:
            ax1.text(x[i], s1[i] + s2[i] + s3[i] / 2, f"{s3[i]:.1f}%", ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(ct.index)
    ax1.set_ylim(0, 103)
    ax1.set_ylabel("Tỷ lệ phân bổ số nguồn báo (%)")
    ax1.set_title("A. Độ phủ đa nguồn tăng mạnh theo quy mô sự kiện", loc="left", pad=10)
    ax1.grid(axis="x", visible=False)
    ax1.legend(loc="upper right", fontsize=8.8)

    # Panel B: Propagation Lead-Lag Cumulative Probability / Distribution (Hours) for 3-source events
    three_ids = set(ev[ev["n_sources"] == 3]["event_id"])
    ae_3 = ae[ae["event_id"].isin(three_ids) & (ae["decision"] != "routine")].copy()
    ae_3["pub_dt"] = pd.to_datetime(ae_3["published_at"], utc=True).dt.tz_localize(None)
    src_first = ae_3.groupby(["event_id", "source"])["pub_dt"].min().unstack()
    times_arr = np.sort(src_first.dropna().to_numpy(dtype="datetime64[s]"), axis=1)
    lag2 = (times_arr[:, 1] - times_arr[:, 0]) / np.timedelta64(1, "h")
    lag3 = (times_arr[:, 2] - times_arr[:, 0]) / np.timedelta64(1, "h")

    # Plot ECDF up to 72 hours for clean readability
    grid_h = np.linspace(0, 72, 300)
    cdf2 = [(lag2 <= h).mean() * 100 for h in grid_h]
    cdf3 = [(lag3 <= h).mean() * 100 for h in grid_h]

    ax2.plot(grid_h, cdf2, color=C_TEAL, linewidth=2.4, label=f"Đến nguồn báo thứ 2 (Trung vị = {np.median(lag2):.2f}h)")
    ax2.plot(grid_h, cdf3, color=C_ORANGE, linewidth=2.4, label=f"Đến nguồn báo thứ 3 (Trung vị = {np.median(lag3):.2f}h)")

    med2, med3 = float(np.median(lag2)), float(np.median(lag3))
    ax2.axvline(med2, color=C_TEAL, linestyle="--", linewidth=1.2)
    ax2.axvline(med3, color=C_ORANGE, linestyle="--", linewidth=1.2)
    ax2.axhline(50, color=C_GRAY, linestyle=":", linewidth=1.0)

    ax2.scatter([med2, med3], [50, 50], color=[C_TEAL, C_ORANGE], zorder=5, s=45)
    ax2.annotate(f"50% sau {med2:.2f}h", xy=(med2, 50), xytext=(med2 + 4, 36),
                 arrowprops=dict(arrowstyle="->", color=C_TEAL), fontsize=8.8, fontweight="bold", color=C_TEAL)
    ax2.annotate(f"50% sau {med3:.2f}h", xy=(med3, 50), xytext=(med3 + 5, 22),
                 arrowprops=dict(arrowstyle="->", color=C_ORANGE), fontsize=8.8, fontweight="bold", color=C_ORANGE)

    # Inset box showing First-Publisher Parity
    inset_text = (
        "Tỷ lệ đăng bài đầu tiên (35.223 sk đa báo):\n"
        "• Thanh Niên: 34.09% (12.009 sk)\n"
        "• Tuổi Trẻ:     34.09% (12.008 sk)\n"
        "• VietnamNet: 31.81% (11.206 sk)"
    )
    ax2.text(
        0.97, 0.12, inset_text, transform=ax2.transAxes,
        ha="right", va="bottom", fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#f8f9fa", edgecolor="#cccccc")
    )

    ax2.set_xlim(0, 72)
    ax2.set_ylim(0, 102)
    ax2.set_xticks([0, 6, 12, 24, 36, 48, 60, 72])
    ax2.set_xlabel("Thời gian trễ kể từ bài báo đầu tiên (Giờ)")
    ax2.set_ylabel("Tỷ lệ sự kiện đã lan tỏa tích lũy (%)")
    ax2.set_title("B. Tốc độ lan truyền tin tức giữa 3 tòa soạn (N = 8.556 sự kiện)", loc="left", pad=10)
    ax2.legend(loc="upper left")

    plt.tight_layout(pad=1.6)
    out = FIG_DIR / "fig3_cross_source_dissemination.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_fig4_lifecycle_and_peak_velocity(ev: pd.DataFrame, ed: pd.DataFrame) -> Path:
    """Figure 4: Scale-Dependent Peak Timing & Event Survival Decay Curve (with Day-4 Cliff)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

    # Panel A: Peak Day distribution across Event Scale Tiers
    idx_max = ed.groupby("event_id")["article_count"].idxmax()
    peaks = ed.loc[idx_max, ["event_id", "event_age_days"]].set_index("event_id")
    ev_p = ev.set_index("event_id").join(peaks)

    def peak_bucket(d):
        if d == 0:
            return "Ngày 0 (Ngay ngày đầu)"
        elif d == 1:
            return "Ngày 1 (Sau 24h)"
        elif d <= 3:
            return "Ngày 2–3"
        else:
            return "Ngày 4–14 (Kéo dài)"

    ev_p["peak_cat"] = ev_p["event_age_days"].map(peak_bucket)
    ev_p["scale_cat"] = pd.cut(
        ev_p["n_articles"],
        bins=[0, 1, 4, 19, 1000],
        labels=["Singleton\n(1 bài)", "Cụm nhỏ\n(2–4 bài)", "Cụm vừa\n(5–19 bài)", "Sự kiện Viral\n(≥20 bài)"]
    )
    cols_order = ["Ngày 0 (Ngay ngày đầu)", "Ngày 1 (Sau 24h)", "Ngày 2–3", "Ngày 4–14 (Kéo dài)"]
    ct_peak = pd.crosstab(ev_p["scale_cat"], ev_p["peak_cat"], normalize="index")[cols_order] * 100

    x = np.arange(len(ct_peak))
    colors_p = ["#9ecae1", C_TEAL, C_ORANGE, C_CRIMSON]
    bottom = np.zeros(len(ct_peak))
    for col, c in zip(cols_order, colors_p):
        vals = ct_peak[col].values
        ax1.bar(x, vals, bottom=bottom, width=0.55, color=c, edgecolor="white", label=col)
        for i, v in enumerate(vals):
            if v >= 9.0:
                txt_color = "#111111" if col == "Ngày 0 (Ngay ngày đầu)" else "white"
                ax1.text(x[i], bottom[i] + v / 2, f"{v:.1f}%", ha="center", va="center", fontsize=8.8, fontweight="bold", color=txt_color)
        bottom += vals

    ax1.set_xticks(x)
    ax1.set_xticklabels(ct_peak.index, fontweight="bold")
    ax1.set_ylim(0, 104)
    ax1.set_ylabel("Tỷ lệ sự kiện đạt đỉnh lượng bài (%)")
    ax1.set_title("A. Thời điểm đạt đỉnh (Peak Timing): Sự kiện lớn cần thời gian tích lũy", loc="left", pad=10)
    ax1.grid(axis="x", visible=False)
    ax1.legend(loc="upper right", fontsize=8.5)

    # Panel B: Survival Curve (Multi-article clusters N >= 2, N=48,212)
    cluster_ids = set(ev[ev["n_articles"] >= 2]["event_id"])
    ed_cl = ed[ed["event_id"].isin(cluster_ids)]
    n_clusters = len(cluster_ids)

    max_age_cl = ed_cl.groupby("event_id")["event_age_days"].max()
    ages = np.arange(15)
    alive_pct = [(max_age_cl >= a).sum() / n_clusters * 100 for a in ages]
    active_pct = [(ed_cl["event_age_days"] == a).sum() / n_clusters * 100 for a in ages]

    ax2.plot(ages, alive_pct, "-o", color=C_BLUE, linewidth=2.3, markersize=5.5,
             label="Sự kiện còn sống ($\\text{max\\_age} \\geq t$)")
    ax2.plot(ages, active_pct, "--s", color=C_GREEN, linewidth=2.0, markersize=5.0,
             label="Sự kiện có bài đăng trong ngày $t$")

    # Highlight Day 3 -> Day 4 Cliff
    ax2.axvspan(3.0, 4.0, color=C_CRIMSON, alpha=0.14, label="Vách đá Ngày 3→4 (-48.3% do max_gap=3d)")
    ax2.annotate(
        f"Ngày 3: {active_pct[3]:.1f}%\n(7.529 sk)",
        xy=(3, active_pct[3]), xytext=(0.6, 9.5),
        arrowprops=dict(arrowstyle="->", color=C_GRAY, lw=1.1), fontsize=8.5, fontweight="bold"
    )
    ax2.annotate(
        f"Ngày 4: {active_pct[4]:.1f}%\n(3.893 sk, -48.3%)",
        xy=(4, active_pct[4]), xytext=(5.2, 18.0),
        arrowprops=dict(arrowstyle="->", color=C_CRIMSON, lw=1.1), fontsize=8.5, fontweight="bold", color=C_CRIMSON
    )

    ax2.set_yscale("log")
    ax2.set_xticks(ages)
    ax2.set_ylim(0.7, 130)
    ax2.yaxis.set_major_formatter(mticker.ScalarFormatter())
    ax2.set_yticks([1, 2, 5, 10, 25, 50, 100])
    ax2.set_xlabel("Tuổi sự kiện (Số ngày kể từ bài đầu tiên)")
    ax2.set_ylabel("Tỷ lệ trong nhóm Cụm đa bài (% trên thang log)")
    ax2.set_title("B. Đường cong sinh tồn sự kiện đa bài & Hiệu ứng ngưỡng 3 ngày", loc="left", pad=10)
    ax2.legend(loc="upper right", fontsize=8.5)

    plt.tight_layout(pad=1.6)
    out = FIG_DIR / "fig4_lifecycle_and_peak_velocity.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_fig5_real_event_archetypes(ev: pd.DataFrame, ed: pd.DataFrame) -> Path:
    """Figure 5: Normalized Lifecycle Archetypes & 4 Real-World Vietnamese News Case Studies."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

    # Panel A: Normalized Daily Share Trajectories for Viral Events (N >= 20, non-sports capped)
    viral_ev = ev[(ev["n_articles"] >= 20) & (ev["duration_days"] >= 2)].copy()
    ed_v = ed[ed["event_id"].isin(viral_ev["event_id"])].copy()
    idx_max = ed_v.groupby("event_id")["article_count"].idxmax()
    peak_days = ed_v.loc[idx_max].set_index("event_id")["event_age_days"]

    # Create dense 0..10 day matrix of daily fraction of total event articles
    tot_map = viral_ev.set_index("event_id")["n_articles"].to_dict()
    piv = ed_v.pivot(index="event_id", columns="event_age_days", values="article_count").reindex(columns=range(15), fill_value=0)
    piv_norm = piv.div(pd.Series(tot_map), axis=0) * 100.0

    g_day0 = piv_norm.loc[peak_days[peak_days == 0].index].mean()
    g_day1_2 = piv_norm.loc[peak_days[peak_days.isin([1, 2])].index].mean()
    g_day3_5 = piv_norm.loc[peak_days[peak_days.isin([3, 4, 5])].index].mean()

    days_show = np.arange(11)
    ax1.plot(days_show, g_day0[days_show], "-o", color=C_CRIMSON, linewidth=2.3,
             label="1. Bùng phát tức thời (Đỉnh Ngày 0)")
    ax1.plot(days_show, g_day1_2[days_show], "-s", color=C_BLUE, linewidth=2.3,
             label="2. Lan tỏa tiêu chuẩn (Đỉnh Ngày 1–2)")
    ax1.plot(days_show, g_day3_5[days_show], "-^", color=C_GREEN, linewidth=2.3,
             label="3. Tích lũy leo thang (Đỉnh Ngày 3–5)")

    ax1.set_xticks(days_show)
    ax1.set_xlabel("Tuổi sự kiện (Ngày 0 → Ngày 10)")
    ax1.set_ylabel("Tỷ trọng bài báo trung bình trong ngày (%)")
    ax1.set_title("A. Ba hình mẫu vòng đời chuẩn hóa của sự kiện lớn (N ≥ 20 bài)", loc="left", pad=10)
    ax1.legend(loc="upper right")

    # Panel B: 4 Real-World Case Studies from the Corpus
    cases = [
        ("E186119", "Bão Kalmaegi đổ bộ Gia Lai (105 bài, đỉnh Ngày 4)", C_BLUE, "-o"),
        ("E268450", "Điểm thi bất thường Tuyên Quang (123 bài, đa đỉnh)", C_CRIMSON, "-s"),
        ("E271857", "Lật ca nô Phú Quốc (61 bài, bùng phát Ngày 0–1)", C_ORANGE, "-^"),
        ("E176852", "Bão số 10 Bualoi (50 bài, ví dụ README, đỉnh Ngày 3)", C_GREEN, "--d"),
    ]
    for eid, label, col, style in cases:
        sub = ed[ed["event_id"] == eid].set_index("event_age_days")["article_count"].reindex(range(13), fill_value=0)
        ax2.plot(range(13), sub.values, style, color=col, linewidth=2.1, markersize=5.0, label=label)

    ax2.annotate(
        "Đổ bộ đất liền\n(33 bài/ngày)",
        xy=(4, 33), xytext=(1.5, 32.0),
        arrowprops=dict(arrowstyle="->", color=C_BLUE, lw=1.1), fontsize=8.5, fontweight="bold", color=C_BLUE
    )
    ax2.annotate(
        "Khởi tố 4 bị can\n(Đỉnh thứ 2: 24 bài)",
        xy=(6, 24), xytext=(6.8, 24.5),
        arrowprops=dict(arrowstyle="->", color=C_CRIMSON, lw=1.1), fontsize=8.5, fontweight="bold", color=C_CRIMSON
    )

    ax2.set_xticks(range(13))
    ax2.set_ylim(0, 41)
    ax2.set_xlabel("Tuổi sự kiện (Ngày kể từ bài báo đầu tiên)")
    ax2.set_ylabel("Số lượng bài báo xuất bản trong ngày")
    ax2.set_title("B. Diễn biến thực tế của 4 sự kiện điển hình trong dữ liệu", loc="left", pad=10)
    ax2.legend(loc="upper right", fontsize=8.2)

    plt.tight_layout(pad=1.6)
    out = FIG_DIR / "fig5_real_event_archetypes.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_fig6_data_quality_anomalies(ev: pd.DataFrame, cov: pd.DataFrame) -> Path:
    """Figure 6: Tuổi Trẻ May 13-15, 2026 Blackout & 14-Day Duration Cap Category Breakdown."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

    # Panel A: May 2026 Daily Coverage showing Tuổi Trẻ Blackout & Phase 5 Masking Window
    may = cov[(cov["date"] >= "2026-05-01") & (cov["date"] <= "2026-05-28")].copy()
    may["dt"] = pd.to_datetime(may["date"])

    ax1.plot(may["dt"], may["Thanh Niên"], color=C_BLUE, linewidth=1.8, label="Thanh Niên (~260 bài/ngày)")
    ax1.plot(may["dt"], may["VietnamNet"], color=C_GREEN, linewidth=1.8, label="VietnamNet (~195 bài/ngày)")
    ax1.plot(may["dt"], may["Tuổi Trẻ"], color=C_CRIMSON, linewidth=2.6, marker="o", markersize=4, label="Tuổi Trẻ (Đứt quãng 13–15/05)")

    ax1.axvspan(pd.Timestamp("2026-05-13"), pd.Timestamp("2026-05-15"), color=C_CRIMSON, alpha=0.25, label="Mất dữ liệu Crawl (0 bài: 13–15/05)")
    ax1.axvspan(pd.Timestamp("2026-05-10"), pd.Timestamp("2026-05-18"), color=C_AMBER, alpha=0.15, label="Vùng loại trừ Phase 5 (10–18/05)")

    ax1.annotate(
        "0 bài báo\n(13–15/05/2026)",
        xy=(pd.Timestamp("2026-05-14"), 4), xytext=(pd.Timestamp("2026-05-18"), 35),
        arrowprops=dict(arrowstyle="->", color=C_CRIMSON, lw=1.2),
        fontsize=8.8, fontweight="bold", color=C_CRIMSON
    )
    ax1.set_title("A. Sự cố mất dữ liệu Tuổi Trẻ (13–15/05/2026) & Cửa sổ lọc mẫu", loc="left", pad=10)
    ax1.set_xlabel("Ngày trong tháng 05/2026")
    ax1.set_ylabel("Số bài báo thu thập trong ngày")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax1.legend(loc="lower left", fontsize=8.2)

    # Panel B: 14-Day Capped Events (N=701) by Category and Average Event Scale
    capped = ev[ev["duration_days"] >= 13.0].copy()
    cat_summary = capped.groupby("category").agg(
        n_capped=("event_id", "count"),
        mean_articles=("n_articles", "mean"),
    ).sort_values("n_capped", ascending=True).tail(7)

    y = np.arange(len(cat_summary))
    bars = ax2.barh(y, cat_summary["n_capped"], color=C_PURPLE, alpha=0.88, height=0.58)
    bars[-1].set_color(C_CRIMSON)  # Highlight Thể thao at the top

    for i, (idx_cat, row) in enumerate(cat_summary.iterrows()):
        cnt = int(row["n_capped"])
        pct = cnt / len(capped) * 100
        avg_art = row["mean_articles"]
        ax2.text(
            cnt + 4, y[i],
            f"{cnt} sk ({pct:.1f}%) — TB {avg_art:.1f} bài/sk",
            va="center", ha="left", fontsize=8.8,
            fontweight="bold" if idx_cat == "Thể thao" else "normal",
            color=C_CRIMSON if idx_cat == "Thể thao" else "#222222"
        )

    ax2.set_yticks(y)
    ax2.set_yticklabels(cat_summary.index, fontweight="bold")
    ax2.set_xlim(0, 290)
    ax2.set_xlabel("Số lượng sự kiện chạm trần thời gian 14 ngày (Tổng N = 701)")
    ax2.set_title("B. Sự kiện chạm trần 14 ngày: Hiện tượng nối chuỗi giải đấu Thể thao", loc="left", pad=10)
    ax2.grid(axis="y", visible=False)

    plt.tight_layout(pad=1.6)
    out = FIG_DIR / "fig6_data_quality_anomalies.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_fig7_emerging_trend_signals(ed: pd.DataFrame, cov: pd.DataFrame) -> Path:
    """Figure 7: Early Signals of 3-Day Emergence & Absolute vs Relative Target Definition."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

    # Compute exact 7d lookback and 3d forward article counts for active event-days
    ed_dt = ed.copy()
    ed_dt["dt"] = pd.to_datetime(ed_dt["date"])
    merged = ed_dt[["event_id", "dt", "article_count"]].merge(
        ed_dt[["event_id", "dt", "article_count"]],
        on="event_id", suffixes=("", "_o")
    )
    merged["diff"] = (merged["dt_o"] - merged["dt"]).dt.days
    v7 = merged[merged["diff"].between(-6, 0)].groupby(["event_id", "dt"])["article_count_o"].sum().rename("v7")
    f3 = merged[merged["diff"].between(1, 3)].groupby(["event_id", "dt"])["article_count_o"].sum().rename("f3")

    df_f = ed_dt.set_index(["event_id", "dt"]).join([v7, f3]).fillna(0).reset_index()
    df_f["year"] = df_f["date"].str.slice(0, 4).astype(int)

    cov_c = cov.copy()
    cov_c["year"] = cov_c["date"].str.slice(0, 4).astype(int)
    cov_c["total"] = cov_c["Tuổi Trẻ"] + cov_c["Thanh Niên"] + cov_c["VietnamNet"]
    ymed = cov_c.groupby("year")["total"].median().to_dict()

    df_f["is_abs"] = (df_f["f3"] >= 10) & (df_f["f3"] >= 2 * df_f["v7"])
    df_f["rel_thresh"] = df_f["year"].map(lambda y: max(5, round(10 * ymed[y] / ymed[2026])))
    df_f["is_rel"] = (df_f["f3"] >= df_f["rel_thresh"]) & (df_f["f3"] >= 2 * df_f["v7"])

    # Panel A: Day-0 Signal Matrix (Source Count & Initial Volume vs Future Follow-up / Emergence)
    day0 = df_f[df_f["is_first_day"]].copy()
    src_stats = day0.groupby("source_count").agg(
        prob_followup=("f3", lambda s: (s >= 1).mean() * 100),
        prob_emerge_rel=("is_rel", lambda s: s.mean() * 100),
        prob_emerge_abs=("is_abs", lambda s: s.mean() * 100),
        n_ev=("event_id", "count"),
    )

    x = np.arange(3)
    w = 0.35
    b1 = ax1.bar(x - w / 2, src_stats["prob_followup"], width=w, color=C_TEAL, label="Có bài tiếp theo trong 3 ngày tới (%)")
    ax1_r = ax1.twinx()
    b2 = ax1_r.bar(x + w / 2, src_stats["prob_emerge_rel"], width=w, color=C_ORANGE, label="Trở thành Emerging Trend (% - trục phải)")
    ax1_r.spines["top"].set_visible(False)
    ax1_r.grid(False)

    for bar in b1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.0, f"{h:.1f}%", ha="center", fontsize=8.8, fontweight="bold", color=C_TEAL)
    for bar in b2:
        h = bar.get_height()
        ax1_r.text(bar.get_x() + bar.get_width() / 2, h + 0.08, f"{h:.2f}%", ha="center", fontsize=8.8, fontweight="bold", color=C_ORANGE)

    ax1.set_xticks(x)
    ax1.set_xticklabels([
        f"1 nguồn báo\n({src_stats.loc[1, 'n_ev']:,} sk)",
        f"2 nguồn báo\n({src_stats.loc[2, 'n_ev']:,} sk)",
        f"Cả 3 nguồn báo\n({src_stats.loc[3, 'n_ev']:,} sk)"
    ], fontweight="bold")
    ax1.set_ylim(0, 48)
    ax1_r.set_ylim(0, 3.3)
    ax1.set_ylabel("Xác suất có bài đưa tin tiếp trong 3 ngày tới (%)", color=C_TEAL)
    ax1_r.set_ylabel("Xác suất bùng nổ thành Emerging Trend (%)", color=C_ORANGE)
    ax1.set_title("A. Tín hiệu sớm Ngày 0: Sự đồng thuận đa báo dự báo bùng nổ", loc="left", pad=10)
    ax1.grid(axis="x", visible=False)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_r.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8.4)

    # Panel B: Positive Label Rate across Years (Absolute Threshold vs Volume-Normalized Threshold)
    yr_stats = df_f.groupby("year").agg(
        abs_rate=("is_abs", lambda s: s.mean() * 100),
        rel_rate=("is_rel", lambda s: s.mean() * 100),
        abs_cnt=("is_abs", "sum"),
        rel_cnt=("is_rel", "sum"),
    )
    xy = np.arange(len(yr_stats))
    b_abs = ax2.bar(xy - w / 2, yr_stats["abs_rate"], width=w, color=C_BLUE, label="Ngưỡng cố định (Future 3d ≥ 10 bài)")
    b_rel = ax2.bar(xy + w / 2, yr_stats["rel_rate"], width=w, color=C_GREEN, label="Ngưỡng chuẩn hóa theo năm (≥5 / ≥5 / ≥5 / ≥10 bài)")

    for i, bar in enumerate(b_abs):
        h = bar.get_height()
        cnt = int(yr_stats["abs_cnt"].iloc[i])
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.015, f"{h:.2f}%\n({cnt})", ha="center", fontsize=8.0, color=C_BLUE, fontweight="bold")
    for i, bar in enumerate(b_rel):
        h = bar.get_height()
        cnt = int(yr_stats["rel_cnt"].iloc[i])
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.015, f"{h:.2f}%\n({cnt})", ha="center", fontsize=8.0, color=C_GREEN, fontweight="bold")

    ax2.set_xticks(xy)
    ax2.set_xticklabels([f"Năm {y}" for y in yr_stats.index], fontweight="bold")
    ax2.set_ylim(0, 0.78)
    ax2.set_ylabel("Tỷ lệ mẫu dương is_emerging_next_3d (%)")
    ax2.set_title("B. So sánh định nghĩa Emerging Trend: Cố định vs. Chuẩn hóa theo năm", loc="left", pad=10)
    ax2.grid(axis="x", visible=False)
    ax2.legend(loc="upper left", fontsize=8.4)

    plt.tight_layout(pad=1.6)
    out = FIG_DIR / "fig7_emerging_trend_signals.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    configure_style()
    print("Loading Phase 4 datasets...")
    ae = pd.read_parquet(DATA_DIR / "article_events.parquet")
    ev = pd.read_parquet(DATA_DIR / "events.parquet")
    ed = pd.read_parquet(DATA_DIR / "event_daily.parquet")
    cov = pd.read_csv(DATA_DIR / "coverage_daily.csv")

    outputs = [
        plot_fig1_scale_and_powerlaw(ev),
        plot_fig2_corpus_drift_and_decisions(ae, ev, cov),
        plot_fig3_cross_source_dissemination(ae, ev),
        plot_fig4_lifecycle_and_peak_velocity(ev, ed),
        plot_fig5_real_event_archetypes(ev, ed),
        plot_fig6_data_quality_anomalies(ev, cov),
        plot_fig7_emerging_trend_signals(ed, cov),
    ]
    for p in outputs:
        print(f"Generated figure: {p} ({p.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
