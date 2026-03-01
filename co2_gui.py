"""
Interactive GUI for CO2 Heat Pump Cycle Analysis.

Provides input fields for the four state points and compressor data,
computes thermodynamic properties via CoolProp, and displays the cycle
on pressure-enthalpy (P-h) and temperature-entropy (T-s) diagrams.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

from co2_cycle import (
    compute_cycle,
    compute_compressor_metrics,
    get_saturation_envelope,
    get_isotherms,
    get_isobars,
)

# ---------------------------------------------------------------------------
# Default values – representative transcritical CO2 heat-pump conditions
# ---------------------------------------------------------------------------
DEFAULTS = {
    "P1": 35.0,   # bar, compressor inlet
    "T1": 5.0,    # °C
    "P2": 100.0,  # bar, compressor outlet
    "T2": 90.0,   # °C
    "P3": 100.0,  # bar, gas-cooler outlet / before throttle
    "T3": 35.0,   # °C
    "P4": 35.0,   # bar, after throttle
    "disp": 10.0,       # m³/h compressor displacement
    "stroke_vol": 0.001, # m³ per stroke
}


class CO2HeatPumpApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("CO₂ Heat Pump Cycle Analyzer")
        self.geometry("1400x820")
        self.minsize(1100, 700)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Left panel: inputs + results
        left = ttk.Frame(self, padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Right panel: plots
        right = ttk.Frame(self, padding=5)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_inputs(left)
        self._build_results(left)
        self._build_plots(right)

    def _build_inputs(self, parent):
        """Create labelled entry fields for the four state points."""
        title = ttk.Label(parent, text="CO₂ Heat Pump Inputs",
                          font=("Helvetica", 14, "bold"))
        title.pack(anchor=tk.W, pady=(0, 8))

        self.entries = {}

        state_labels = [
            ("State 1 – Compressor Inlet", [
                ("P1", "Pressure (bar)"),
                ("T1", "Temperature (°C)"),
            ]),
            ("State 2 – Compressor Outlet", [
                ("P2", "Pressure (bar)"),
                ("T2", "Temperature (°C)"),
            ]),
            ("State 3 – Before Throttle Valve", [
                ("P3", "Pressure (bar)"),
                ("T3", "Temperature (°C)"),
            ]),
            ("State 4 – After Throttle Valve", [
                ("P4", "Pressure (bar)"),
            ]),
        ]

        for group_label, fields in state_labels:
            lf = ttk.LabelFrame(parent, text=group_label, padding=5)
            lf.pack(fill=tk.X, pady=3)
            for key, label in fields:
                row = ttk.Frame(lf)
                row.pack(fill=tk.X, pady=1)
                ttk.Label(row, text=label, width=20).pack(side=tk.LEFT)
                var = tk.StringVar(value=str(DEFAULTS[key]))
                entry = ttk.Entry(row, textvariable=var, width=12)
                entry.pack(side=tk.LEFT, padx=4)
                self.entries[key] = var

        # Compressor info
        lf = ttk.LabelFrame(parent, text="Compressor", padding=5)
        lf.pack(fill=tk.X, pady=3)
        for key, label in [("disp", "Displacement (m³/h)"),
                           ("stroke_vol", "Stroke volume (m³)")]:
            row = ttk.Frame(lf)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=label, width=20).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(DEFAULTS[key]))
            entry = ttk.Entry(row, textvariable=var, width=12)
            entry.pack(side=tk.LEFT, padx=4)
            self.entries[key] = var

        note = ttk.Label(parent,
                         text="State 4 temperature is determined\n"
                              "from pressure (evaporation T).",
                         foreground="gray")
        note.pack(anchor=tk.W, pady=4)

        btn = ttk.Button(parent, text="Calculate & Plot",
                         command=self._on_calculate)
        btn.pack(fill=tk.X, pady=6)

    def _build_results(self, parent):
        """Text widget showing computed results."""
        lf = ttk.LabelFrame(parent, text="Results", padding=5)
        lf.pack(fill=tk.BOTH, expand=True, pady=4)
        self.results_text = tk.Text(lf, width=38, height=18,
                                    font=("Courier", 9), state=tk.DISABLED)
        self.results_text.pack(fill=tk.BOTH, expand=True)

    def _build_plots(self, parent):
        """Matplotlib figure embedded in the Tk window."""
        self.fig = Figure(figsize=(9, 7), dpi=100)
        self.ax_ph = self.fig.add_subplot(2, 1, 1)
        self.ax_ts = self.fig.add_subplot(2, 1, 2)
        self.fig.subplots_adjust(hspace=0.35, left=0.10,
                                 right=0.96, top=0.95, bottom=0.08)

        canvas = FigureCanvasTkAgg(self.fig, master=parent)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas = canvas

        toolbar = NavigationToolbar2Tk(canvas, parent)
        toolbar.update()

    # ------------------------------------------------------------------
    # Calculation & plotting
    # ------------------------------------------------------------------
    def _read_float(self, key):
        """Read a float from an entry, raising ValueError on failure."""
        try:
            return float(self.entries[key].get())
        except ValueError:
            raise ValueError(f"Invalid number for {key}")

    def _on_calculate(self):
        """Run the cycle calculation and update plots + results."""
        try:
            P1 = self._read_float("P1")
            T1 = self._read_float("T1")
            P2 = self._read_float("P2")
            T2 = self._read_float("T2")
            P3 = self._read_float("P3")
            T3 = self._read_float("T3")
            P4 = self._read_float("P4")
            disp = self._read_float("disp")
            sv = self._read_float("stroke_vol")
        except ValueError as exc:
            messagebox.showerror("Input Error", str(exc))
            return

        try:
            cycle = compute_cycle(P1, T1, P2, T2, P3, T3, P4)
            comp = compute_compressor_metrics(cycle, disp, sv)
        except Exception as exc:
            messagebox.showerror("Calculation Error", str(exc))
            return

        self._update_results(cycle, comp)
        self._update_plots(cycle)

    def _update_results(self, cycle, comp):
        """Fill the results text widget."""
        states = cycle["states"]
        lines = []
        labels = ["1-Comp.In", "2-Comp.Out", "3-Pre-Throt", "4-Post-Throt"]
        lines.append(f"{'Point':<14} {'P(bar)':>8} {'T(°C)':>8} "
                     f"{'h(kJ/kg)':>10} {'s(kJ/kgK)':>10}")
        lines.append("-" * 56)
        for lbl, st in zip(labels, states):
            lines.append(
                f"{lbl:<14} {st['P_bar']:8.1f} {st['T_C']:8.2f} "
                f"{st['h']/1e3:10.2f} {st['s']/1e3:10.4f}"
            )
        lines.append("")
        lines.append(f"Compressor work:    {cycle['w_comp']/1e3:8.2f} kJ/kg")
        lines.append(f"Gas-cooler heat:    {cycle['q_gc']/1e3:8.2f} kJ/kg")
        lines.append(f"Evaporator heat:    {cycle['q_evap']/1e3:8.2f} kJ/kg")
        lines.append(f"COP (heating):      {cycle['cop_heating']:8.3f}")
        lines.append(f"COP (cooling):      {cycle['cop_cooling']:8.3f}")
        lines.append("")
        lines.append(f"Mass flow rate:     {comp['mass_flow']:8.4f} kg/s")
        lines.append(f"Heating capacity:   {comp['heating_capacity']/1e3:8.2f} kW")
        lines.append(f"Cooling capacity:   {comp['cooling_capacity']/1e3:8.2f} kW")
        lines.append(f"Compressor power:   {comp['compressor_power']/1e3:8.2f} kW")
        lines.append(f"Compressor RPM:     {comp['rpm']:8.1f}")
        lines.append(f"Suction density:    {comp['rho_suction']:8.2f} kg/m³")

        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert(tk.END, "\n".join(lines))
        self.results_text.config(state=tk.DISABLED)

    def _update_plots(self, cycle):
        """Draw P-h and T-s diagrams."""
        states = cycle["states"]
        h_pts = [s["h"] / 1e3 for s in states]  # kJ/kg
        P_pts = [s["P"] / 1e5 for s in states]   # bar
        s_pts = [s["s"] / 1e3 for s in states]   # kJ/(kg·K)
        T_pts = [s["T"] - 273.15 for s in states]  # °C

        # Close the cycle for plotting
        h_cycle = h_pts + [h_pts[0]]
        P_cycle = P_pts + [P_pts[0]]
        s_cycle = s_pts + [s_pts[0]]
        T_cycle = T_pts + [T_pts[0]]

        envelope = get_saturation_envelope()

        # ---- P-h diagram ----
        ax = self.ax_ph
        ax.clear()
        # Saturation dome
        ax.plot(envelope["h_f"] / 1e3, envelope["P_sat"] / 1e5,
                "b-", linewidth=1.2, label="Sat. liquid")
        ax.plot(envelope["h_g"] / 1e3, envelope["P_sat"] / 1e5,
                "r-", linewidth=1.2, label="Sat. vapor")
        # Cycle
        ax.plot(h_cycle, P_cycle, "ko-", linewidth=2, markersize=7,
                label="Cycle", zorder=5)
        # Annotate states
        offsets = [(-15, -18), (10, 8), (-15, 8), (10, -18)]
        for i, (lbl, (xo, yo)) in enumerate(
                zip(["1", "2", "3", "4"], offsets)):
            ax.annotate(lbl, (h_pts[i], P_pts[i]),
                        textcoords="offset points", xytext=(xo, yo),
                        fontsize=11, fontweight="bold",
                        arrowprops=dict(arrowstyle="->", color="gray"))
        # Process labels along each line segment
        mid_labels = ["Compression", "Gas cooler", "Throttle", "Evaporator"]
        for i in range(4):
            j = (i + 1) % 4
            mx = (h_pts[i] + h_pts[j]) / 2
            my = (P_pts[i] + P_pts[j]) / 2
            ax.text(mx, my, mid_labels[i], fontsize=7, color="purple",
                    ha="center", va="bottom",
                    bbox=dict(fc="white", ec="none", alpha=0.7))

        ax.set_xlabel("Specific Enthalpy  h (kJ/kg)")
        ax.set_ylabel("Pressure  P (bar)")
        ax.set_yscale("log")
        ax.set_title("P – h  Diagram (CO₂ Heat Pump Cycle)")
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(True, which="both", linestyle=":", alpha=0.5)

        # ---- T-s diagram ----
        ax2 = self.ax_ts
        ax2.clear()
        # Saturation dome
        ax2.plot(envelope["s_f"] / 1e3, envelope["T_sat"] - 273.15,
                 "b-", linewidth=1.2, label="Sat. liquid")
        ax2.plot(envelope["s_g"] / 1e3, envelope["T_sat"] - 273.15,
                 "r-", linewidth=1.2, label="Sat. vapor")
        # Cycle
        ax2.plot(s_cycle, T_cycle, "ko-", linewidth=2, markersize=7,
                 label="Cycle", zorder=5)
        for i, (lbl, (xo, yo)) in enumerate(
                zip(["1", "2", "3", "4"], offsets)):
            ax2.annotate(lbl, (s_pts[i], T_pts[i]),
                         textcoords="offset points", xytext=(xo, yo),
                         fontsize=11, fontweight="bold",
                         arrowprops=dict(arrowstyle="->", color="gray"))
        for i in range(4):
            j = (i + 1) % 4
            mx = (s_pts[i] + s_pts[j]) / 2
            my = (T_pts[i] + T_pts[j]) / 2
            ax2.text(mx, my, mid_labels[i], fontsize=7, color="purple",
                     ha="center", va="bottom",
                     bbox=dict(fc="white", ec="none", alpha=0.7))

        ax2.set_xlabel("Specific Entropy  s (kJ/(kg·K))")
        ax2.set_ylabel("Temperature  T (°C)")
        ax2.set_title("T – s  Diagram (CO₂ Heat Pump Cycle)")
        ax2.legend(fontsize=8, loc="lower right")
        ax2.grid(True, linestyle=":", alpha=0.5)

        self.canvas.draw()


def main():
    app = CO2HeatPumpApp()
    app.mainloop()


if __name__ == "__main__":
    main()
