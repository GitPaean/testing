# CO₂ Heat Pump Cycle Analyzer

Interactive GUI application for analyzing the thermodynamic cycle of a
transcritical CO₂ heat pump.  Enter measured state-point data and compressor
specifications, and the tool computes the full cycle and draws **P–h** and
**T–s** diagrams.

![P-h and T-s diagrams](https://github.com/user-attachments/assets/0843fcba-b4fb-4d8f-b363-ebec85861e47)

## Features

* Four state-point inputs (pressure & temperature at compressor inlet/outlet,
  before throttle valve, and pressure after throttle valve).
* Compressor inputs (displacement in m³/h, stroke volume in m³, 4 strokes).
* Thermodynamic properties computed with **CoolProp** (enthalpy, entropy,
  density, quality).
* Automatic determination of evaporating temperature from pressure (state 4).
* **P–h diagram** with logarithmic pressure axis and saturation dome.
* **T–s diagram** with saturation dome.
* Computed performance metrics: COP (heating & cooling), mass flow rate,
  heating/cooling capacity, compressor power, RPM.

## Requirements

* Python ≥ 3.9
* Packages listed in `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python co2_gui.py
```

1. Enter the measured pressures and temperatures for states 1–3 and the
   pressure for state 4.
2. Enter the compressor displacement and stroke volume.
3. Click **Calculate & Plot**.

## Running Tests

```bash
python -m unittest test_co2_cycle -v
```

## File Overview

| File | Description |
|------|-------------|
| `co2_cycle.py` | Thermodynamic cycle calculations (CoolProp wrapper) |
| `co2_gui.py` | Tkinter GUI application |
| `test_co2_cycle.py` | Unit tests for the cycle calculations |
| `requirements.txt` | Python dependencies |
