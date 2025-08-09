from __future__ import annotations
from typing import Optional, Dict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np


def _style_axes(ax, title: str, ylabel: str = "PnL"):
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(ax.xaxis.get_major_locator())
    )
    for label in ax.get_xticklabels():
        label.set_rotation(45)
    
    # Улучшаем внешний вид
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['bottom'].set_linewidth(0.5)


def plot_cumulative_series(df: pd.DataFrame, show: bool = False, save_path: Optional[str] = None):
    """Legacy: three separate figures for realized/unrealized/gross."""
    plt.style.use('seaborn-v0_8-whitegrid')
    
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(df["ts"], df["realized_total"], label="Realized (total)", 
             linewidth=2.5, color='#2E8B57')
    ax1.fill_between(df["ts"], df["realized_total"], alpha=0.3, color='#2E8B57')
    _style_axes(ax1, "Realized PnL (total)")
    ax1.legend(frameon=True, fancybox=True, shadow=True)
    if save_path:
        fig1.savefig(f"{save_path}_realized.png", bbox_inches="tight", dpi=300)

    fig2, ax2 = plt.subplots(figsize=(12, 6))
    ax2.plot(df["ts"], df["unrealized_total"], label="Unrealized", 
             linewidth=2.5, color='#4169E1')
    ax2.fill_between(df["ts"], df["unrealized_total"], alpha=0.3, color='#4169E1')
    _style_axes(ax2, "Unrealized PnL")
    ax2.legend(frameon=True, fancybox=True, shadow=True)
    if save_path:
        fig2.savefig(f"{save_path}_unrealized.png", bbox_inches="tight", dpi=300)

    fig3, ax3 = plt.subplots(figsize=(12, 6))
    ax3.plot(df["ts"], df["gross_total"], label="Gross (total)", 
             linewidth=2.5, color='#8B008B')
    ax3.fill_between(df["ts"], df["gross_total"], alpha=0.3, color='#8B008B')
    _style_axes(ax3, "Gross PnL")
    ax3.legend(frameon=True, fancybox=True, shadow=True)
    if save_path:
        fig3.savefig(f"{save_path}_gross.png", bbox_inches="tight", dpi=300)

    if show:
        plt.show()

    return fig1, fig2, fig3


def _plot_combined(df: pd.DataFrame, show: bool = False, save_path: Optional[str] = None):
    """Single colorful chart with all three series."""
    plt.style.use('seaborn-v0_8-whitegrid')
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Используем более красивые цвета
    ax.plot(df["ts"], df["realized_total"], label="Realized", 
            linewidth=3.0, color='#2E8B57', alpha=0.8)
    ax.plot(df["ts"], df["unrealized_total"], label="Unrealized", 
            linewidth=3.0, color='#4169E1', alpha=0.8)
    ax.plot(df["ts"], df["gross_total"], label="Gross", 
            linewidth=3.5, color='#8B008B', alpha=0.9)
    
    # Добавляем заливку для лучшей визуализации
    ax.fill_between(df["ts"], df["gross_total"], alpha=0.2, color='#8B008B')
    
    _style_axes(ax, "PnL Overview (Realized + Unrealized + Gross)")
    ax.legend(frameon=True, fancybox=True, shadow=True, fontsize=11)
    
    if save_path:
        fig.savefig(f"{save_path}_combined.png", bbox_inches="tight", dpi=300)
    if show:
        plt.show()
    return fig


def _plot_per_symbol(df: pd.DataFrame, show: bool = False, save_dir: Optional[str] = None) -> Dict[str, plt.Figure]:
    """One figure per symbol with all three series."""
    plt.style.use('seaborn-v0_8-whitegrid')
    
    figures: Dict[str, plt.Figure] = {}
    grouped = df.groupby("symbol", sort=False)
    for sym, g in grouped:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(g["ts"], g["realized_total"], label="Realized", 
                linewidth=2.5, color='#2E8B57')
        ax.plot(g["ts"], g["unrealized_total"], label="Unrealized", 
                linewidth=2.5, color='#4169E1')
        ax.plot(g["ts"], g["gross_total"], label="Gross", 
                linewidth=3.0, color='#8B008B')
        
        ax.fill_between(g["ts"], g["gross_total"], alpha=0.2, color='#8B008B')
        
        _style_axes(ax, f"{sym} — PnL")
        ax.legend(frameon=True, fancybox=True, shadow=True)
        figures[sym] = fig
        if save_dir:
            out = Path(save_dir) / f"pnl_{sym}.png"
            fig.savefig(out, bbox_inches="tight", dpi=300)
    if show and figures:
        plt.show()
    return figures


def plot_combined(df: pd.DataFrame, show: bool = False, save_path: Optional[str] = None,
                         show_unrealized_bars: bool = True):
    """Portfolio-level: gross_total as line+fill, gross_symbol as bars."""
    plt.style.use('default')
    
    fig, ax1 = plt.subplots(figsize=(14, 8))
    
    # Вычисляем ширину баров динамически
    if len(df) > 1:
        time_diff = (df["ts"].iloc[1] - df["ts"].iloc[0]).total_seconds() / 86400
        bar_width = time_diff * 0.6
    else:
        bar_width = 1
    
    # Создаем бары для gross PnL в моменте (сумма realized + unrealized)
    colors = ['#32CD32' if x >= 0 else '#FF4500' for x in df["gross_symbol"]]
    bars = ax1.bar(df["ts"], df["gross_symbol"], width=bar_width, 
                   color=colors, alpha=0.8, label="PnL", edgecolor='black', linewidth=0.3)
    
    # Улучшаем стилизацию осей
    ax1.set_title("Portfolio PnL Overview", fontsize=16, fontweight='bold', pad=20)
    ax1.set_xlabel("Date", fontsize=12)
    ax1.set_ylabel("PnL", fontsize=12)
    ax1.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
    
    # Настройка осей дат
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    for label in ax1.get_xticklabels():
        label.set_rotation(45)
    
    # Создаем вторую ось Y для кумулятивной линии
    ax2 = ax1.twinx()
    
    # Кумулятивная линия realized_total на второй оси
    line = ax2.plot(df["ts"], df["gross_total"], color='#9370DB', linewidth=2.5, 
                    label="Cumulative Gross PnL", alpha=0.8, marker='o', markersize=4)
    ax2.fill_between(df["ts"], df["gross_total"], alpha=0.3, color='#9370DB')
    
    # Настройка второй оси
    ax2.set_ylabel("Cumulative Gross PnL", fontsize=12, color='#9370DB')
    ax2.tick_params(axis='y', labelcolor='#9370DB')
    
    # Выравниваем нули на обеих осях
    y1_min, y1_max = ax1.get_ylim()
    y2_min, y2_max = ax2.get_ylim()
    
    # Находим максимальные отклонения от нуля для обеих осей
    y1_abs_max = max(abs(y1_min), abs(y1_max))
    y2_abs_max = max(abs(y2_min), abs(y2_max))
    
    # Устанавливаем симметричные пределы относительно нуля
    ax1.set_ylim(-y1_abs_max * 1.1, y1_abs_max * 1.1)
    ax2.set_ylim(-y2_abs_max * 1.1, y2_abs_max * 1.1)
    
    # Убираем верхнюю и правую границы
    ax1.spines['top'].set_visible(False)
    ax2.spines['top'].set_visible(False)
    
    # Легенды для обеих осей
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, 
              fancybox=True, shadow=True, fontsize=10)

    if save_path:
        fig.savefig(f"{save_path}.png", bbox_inches="tight", dpi=300)
    if show:
        plt.show()
    return fig


def plot_per_symbol(df: pd.DataFrame, show: bool = False, save_dir: Optional[str] = None,
                           show_unrealized_bars: bool = True) -> Dict[str, plt.Figure]:
    """Per-symbol pretty plot."""
    plt.style.use('default')
    
    figures: Dict[str, plt.Figure] = {}
    grouped = df.groupby("symbol", sort=False)
    
    for sym, g in grouped:
        fig, ax1 = plt.subplots(figsize=(12, 6))
        
        # Динамическая ширина баров
        if len(g) > 1:
            time_diff = (g["ts"].iloc[1] - g["ts"].iloc[0]).total_seconds() / 86400
            bar_width = time_diff * 0.5
        else:
            bar_width = 1
        
        # Бары для gross PnL в моменте
        colors = ['#32CD32' if x >= 0 else '#FF4500' for x in g["gross_symbol"]]
        bars = ax1.bar(g["ts"], g["gross_symbol"], width=bar_width, 
                       color=colors, alpha=0.8, label="PnL", 
                       edgecolor='black', linewidth=0.3)
        
        # Стилизация
        ax1.set_title(f"{sym} — PnL Overview", fontsize=14, fontweight='bold', pad=20)
        ax1.set_xlabel("Date", fontsize=11)
        ax1.set_ylabel("PnL", fontsize=11)
        ax1.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
        
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        for label in ax1.get_xticklabels():
            label.set_rotation(45)
        
        # Вторая ось Y для кумулятивной линии
        ax2 = ax1.twinx()
        
        # Кумулятивная линия gross_total_symbol на второй оси (для конкретного символа)
        ax2.plot(g["ts"], g["gross_total_symbol"], color='#9370DB', linewidth=2.5, 
                 label="Cumulative Gross PnL", alpha=0.8, marker='o', markersize=3)
        ax2.fill_between(g["ts"], g["gross_total_symbol"], alpha=0.3, color='#9370DB')
        
        ax2.set_ylabel("Cumulative Gross PnL", fontsize=11, color='#9370DB')
        ax2.tick_params(axis='y', labelcolor='#9370DB')
        
        # Выравниваем нули на обеих осях
        y1_min, y1_max = ax1.get_ylim()
        y2_min, y2_max = ax2.get_ylim()
        
        # Находим максимальные отклонения от нуля для обеих осей
        y1_abs_max = max(abs(y1_min), abs(y1_max))
        y2_abs_max = max(abs(y2_min), abs(y2_max))
        
        # Устанавливаем симметричные пределы относительно нуля
        ax1.set_ylim(-y1_abs_max * 1.1, y1_abs_max * 1.1)
        ax2.set_ylim(-y2_abs_max * 1.1, y2_abs_max * 1.1)
        
        # Границы
        ax1.spines['top'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        
        # Легенды для обеих осей
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, 
                  fancybox=True, shadow=True, fontsize=9)
        
        figures[sym] = fig
        if save_dir:
            out = Path(save_dir) / f"pnl_{sym}.png"
            fig.savefig(out, bbox_inches="tight", dpi=300)
    
    if show and figures:
        plt.show()
    return figures