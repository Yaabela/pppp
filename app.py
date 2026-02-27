import streamlit as st
import numpy as np
import pandas as pd


# ----------------------------
# Core power-flow functionality
# ----------------------------
def polar_to_complex(v_mag: float, v_ang_deg: float) -> complex:
    ang = np.radians(v_ang_deg)
    return v_mag * (np.cos(ang) + 1j * np.sin(ang))


def build_y_bus(n_buses: int, lines_df: pd.DataFrame, buses_df: pd.DataFrame) -> np.ndarray:
    """
    Y-bus with:
    - series impedance (R + jX)
    - line charging B/2 at each end (jB/2)
    - off-nominal tap ratio and phase shift
    - bus shunts (G + jB) on diagonal
    """
    y_bus = np.zeros((n_buses, n_buses), dtype=complex)

    for _, row in lines_df.iterrows():
        i = int(row["From"]) - 1
        j = int(row["To"]) - 1

        r = float(row["R"])
        x = float(row["X"])
        b_total = float(row["B_total"])
        tap = float(row["Tap"])
        shift_deg = float(row["Shift_deg"])

        z = complex(r, x)
        y = 1 / z
        y_sh_half = 1j * (b_total / 2.0)

        if tap <= 0:
            tap = 1.0
        shift_rad = np.radians(shift_deg)
        a = tap * np.exp(1j * shift_rad)  # complex tap

        # Stamping with complex off-nominal tap
        y_bus[i, i] += (y + y_sh_half) / (a * np.conj(a))
        y_bus[j, j] += y + y_sh_half
        y_bus[i, j] += -y / np.conj(a)
        y_bus[j, i] += -y / a

    # Bus shunts
    for idx, row in buses_df.iterrows():
        g_sh = float(row["G_sh"])
        b_sh = float(row["B_sh"])
        y_bus[idx, idx] += complex(g_sh, b_sh)

    return y_bus


def validate_inputs(n_buses: int, buses_df: pd.DataFrame, lines_df: pd.DataFrame):
    errors = []

    slack_count = (buses_df["Type"] == "Slack").sum()
    if slack_count != 1:
        errors.append(f"Exactly one Slack bus is required. Found {slack_count}.")

    for _, row in lines_df.iterrows():
        f = int(row["From"])
        t = int(row["To"])
        r = float(row["R"])
        x = float(row["X"])

        if f == t:
            errors.append(f"Invalid line ({f}->{t}): From and To cannot be the same.")
        if abs(r) < 1e-12 and abs(x) < 1e-12:
            errors.append(f"Invalid line ({f}->{t}): R and X cannot both be zero.")

    # Basic connectivity check (using line endpoints)
    graph = {i: set() for i in range(1, n_buses + 1)}
    for _, row in lines_df.iterrows():
        f = int(row["From"])
        t = int(row["To"])
        graph[f].add(t)
        graph[t].add(f)

    visited = set()
    stack = [1]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(graph[node] - visited)

    if len(visited) != n_buses:
        errors.append("Network is disconnected. All buses must be electrically connected.")

    return errors


def run_gauss_seidel(
    buses_df: pd.DataFrame,
    lines_df: pd.DataFrame,
    tol_v: float,
    tol_pq: float,
    max_iter: int,
    accel: float
):
    n_buses = len(buses_df)
    y_bus = build_y_bus(n_buses, lines_df, buses_df)

    bus_types = buses_df["Type"].tolist()
    mode = bus_types.copy()  # can change PV -> PQ if Q limits hit

    # Initialize voltages
    v = np.array(
        [polar_to_complex(row["V_set"], row["Angle_set_deg"]) for _, row in buses_df.iterrows()],
        dtype=complex
    )

    # Specified net injections (generation - load), in pu
    p_spec = (buses_df["Pg"] - buses_df["Pl"]).to_numpy(dtype=float)
    q_spec = (buses_df["Qg"] - buses_df["Ql"]).to_numpy(dtype=float)

    q_min = buses_df["Qmin"].to_numpy(dtype=float)
    q_max = buses_df["Qmax"].to_numpy(dtype=float)
    v_set = buses_df["V_set"].to_numpy(dtype=float)

    history = []
    converged = False

    for it in range(1, max_iter + 1):
        max_dv = 0.0

        for i in range(n_buses):
            if bus_types[i] == "Slack":
                continue

            sum_yv = np.dot(y_bus[i, :], v) - y_bus[i, i] * v[i]

            # For PV, estimate Q from current voltage and Ybus
            if mode[i] == "PV":
                i_inj = np.dot(y_bus[i, :], v)
                s_inj = v[i] * np.conj(i_inj)
                q_calc = np.imag(s_inj)

                # Enforce Q limits: if violated, convert to PQ at limit
                if q_calc < q_min[i]:
                    q_use = q_min[i]
                    mode[i] = "PQ"
                elif q_calc > q_max[i]:
                    q_use = q_max[i]
                    mode[i] = "PQ"
                else:
                    q_use = q_calc
            else:
                q_use = q_spec[i]

            v_old = v[i]
            v_raw = (1.0 / y_bus[i, i]) * (((p_spec[i] - 1j * q_use) / np.conj(v_old)) - sum_yv)

            # Acceleration
            v_new = v_old + accel * (v_raw - v_old)

            # If still PV, force voltage magnitude setpoint
            if mode[i] == "PV":
                if abs(v_new) < 1e-12:
                    v_new = polar_to_complex(v_set[i], np.degrees(np.angle(v_old)))
                else:
                    v_new = v_set[i] * np.exp(1j * np.angle(v_new))

            v[i] = v_new
            max_dv = max(max_dv, abs(v_new - v_old))

        # Mismatch calculation
        i_vec = y_bus @ v
        s_calc = v * np.conj(i_vec)
        p_calc = np.real(s_calc)
        q_calc_all = np.imag(s_calc)

        mismatches = []
        for i in range(n_buses):
            if bus_types[i] == "Slack":
                continue
            mismatches.append(abs(p_spec[i] - p_calc[i]))
            if mode[i] == "PQ":
                q_target = q_spec[i]
                mismatches.append(abs(q_target - q_calc_all[i]))

        max_mismatch = max(mismatches) if mismatches else 0.0
        history.append({"Iteration": it, "Max |dV|": max_dv, "Max mismatch": max_mismatch})

        if max_dv < tol_v and max_mismatch < tol_pq:
            converged = True
            break

    # Final calculations
    i_vec = y_bus @ v
    s_calc = v * np.conj(i_vec)
    p_calc = np.real(s_calc)
    q_calc = np.imag(s_calc)

    results = []
    for i in range(n_buses):
        results.append(
            {
                "Bus": i + 1,
                "Type (input)": bus_types[i],
                "Type (final)": mode[i] if bus_types[i] != "Slack" else "Slack",
                "V Magnitude (pu)": abs(v[i]),
                "V Angle (deg)": np.degrees(np.angle(v[i])),
                "P_spec (pu)": p_spec[i],
                "Q_spec (pu)": q_spec[i],
                "P_calc (pu)": p_calc[i],
                "Q_calc (pu)": q_calc[i],
                "dP (pu)": p_spec[i] - p_calc[i],
                "dQ (pu)": q_spec[i] - q_calc[i],
            }
        )

    return {
        "converged": converged,
        "iterations": len(history),
        "history_df": pd.DataFrame(history),
        "results_df": pd.DataFrame(results),
        "y_bus": y_bus,
    }


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Gauss-Seidel Power Flow", layout="wide")
st.title("Gauss-Seidel Power Flow Solver")
st.markdown("Supports Slack, PV, PQ buses with validation and convergence diagnostics.")

st.sidebar.header("Solver Settings")
n_buses = int(st.sidebar.number_input("Number of Buses", min_value=2, value=3, step=1))
tol_v = float(st.sidebar.number_input("Voltage tolerance (|dV|)", value=1e-6, format="%.1e"))
tol_pq = float(st.sidebar.number_input("Power mismatch tolerance", value=1e-6, format="%.1e"))
max_iter = int(st.sidebar.number_input("Max Iterations", min_value=1, value=100, step=1))
accel = float(st.sidebar.number_input("Acceleration factor (1.0-1.9)", min_value=0.5, max_value=1.95, value=1.3, step=0.05))

col1, col2 = st.columns(2)

with col1:
    st.subheader("1) Bus Data")
    bus_rows = []
    for i in range(n_buses):
        with st.expander(f"Bus {i + 1}", expanded=(i == 0)):
            b_type = st.selectbox("Type", ["Slack", "PV", "PQ"], key=f"type_{i}")

            if b_type == "Slack":
                v_set = st.number_input("V set (pu)", value=1.04, key=f"vset_{i}")
                ang_set = st.number_input("Angle set (deg)", value=0.0, key=f"ang_{i}")
            elif b_type == "PV":
                v_set = st.number_input("V set (pu)", value=1.01, key=f"vset_{i}")
                ang_set = st.number_input("Initial angle (deg)", value=0.0, key=f"ang_{i}")
            else:
                v_set = st.number_input("Initial V (pu)", value=1.0, key=f"vset_{i}")
                ang_set = st.number_input("Initial angle (deg)", value=0.0, key=f"ang_{i}")

            pg = st.number_input("Pg (pu)", value=0.0 if b_type == "PQ" else 0.8, key=f"pg_{i}")
            qg = st.number_input("Qg (pu)", value=0.0, key=f"qg_{i}")
            pl = st.number_input("Pl (pu)", value=0.0 if b_type != "PQ" else 0.5, key=f"pl_{i}")
            ql = st.number_input("Ql (pu)", value=0.0 if b_type != "PQ" else 0.2, key=f"ql_{i}")

            if b_type == "PV":
                qmin = st.number_input("Qmin (pu)", value=-0.5, key=f"qmin_{i}")
                qmax = st.number_input("Qmax (pu)", value=0.5, key=f"qmax_{i}")
            else:
                qmin = st.number_input("Qmin (pu)", value=-999.0, key=f"qmin_{i}")
                qmax = st.number_input("Qmax (pu)", value=999.0, key=f"qmax_{i}")

            g_sh = st.number_input("Bus shunt G (pu)", value=0.0, format="%.5f", key=f"gsh_{i}")
            b_sh = st.number_input("Bus shunt B (pu)", value=0.0, format="%.5f", key=f"bsh_{i}")

            bus_rows.append(
                {
                    "Bus": i + 1,
                    "Type": b_type,
                    "V_set": float(v_set),
                    "Angle_set_deg": float(ang_set),
                    "Pg": float(pg),
                    "Qg": float(qg),
                    "Pl": float(pl),
                    "Ql": float(ql),
                    "Qmin": float(qmin),
                    "Qmax": float(qmax),
                    "G_sh": float(g_sh),
                    "B_sh": float(b_sh),
                }
            )

    buses_df = pd.DataFrame(bus_rows)

with col2:
    st.subheader("2) Line Data")
    n_lines = int(st.number_input("Number of Lines", min_value=1, value=max(1, n_buses - 1), step=1))
    line_rows = []
    for i in range(n_lines):
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, c6 = st.columns(2)

        f = c1.number_input("From", min_value=1, max_value=n_buses, value=1, key=f"f_{i}")
        t = c2.number_input("To", min_value=1, max_value=n_buses, value=min(2, n_buses), key=f"t_{i}")
        r = c3.number_input("R (pu)", value=0.02, format="%.5f", key=f"r_{i}")
        x = c4.number_input("X (pu)", value=0.06, format="%.5f", key=f"x_{i}")
        b_total = c5.number_input("B_total (pu)", value=0.03, format="%.5f", key=f"b_{i}")
        tap = c6.number_input("Tap ratio", value=1.0, format="%.4f", key=f"tap_{i}")

        shift_deg = st.number_input("Phase shift (deg)", value=0.0, format="%.3f", key=f"shift_{i}")

        line_rows.append(
            {
                "From": int(f),
                "To": int(t),
                "R": float(r),
                "X": float(x),
                "B_total": float(b_total),
                "Tap": float(tap),
                "Shift_deg": float(shift_deg),
            }
        )

    lines_df = pd.DataFrame(line_rows)

if st.button("Run Power Flow"):
    input_errors = validate_inputs(n_buses, buses_df, lines_df)
    if input_errors:
        for err in input_errors:
            st.error(err)
    else:
        out = run_gauss_seidel(
            buses_df=buses_df,
            lines_df=lines_df,
            tol_v=tol_v,
            tol_pq=tol_pq,
            max_iter=max_iter,
            accel=accel,
        )

        if out["converged"]:
            st.success(f"Converged in {out['iterations']} iterations.")
        else:
            st.warning(f"Did not converge in {out['iterations']} iterations.")

        st.subheader("Bus Results")
        show_df = out["results_df"].copy()
        num_cols = [
            "V Magnitude (pu)", "V Angle (deg)", "P_spec (pu)", "Q_spec (pu)",
            "P_calc (pu)", "Q_calc (pu)", "dP (pu)", "dQ (pu)"
        ]
        for c in num_cols:
            show_df[c] = show_df[c].round(6)
        st.dataframe(show_df, use_container_width=True)

        st.subheader("Convergence History")
        hist_df = out["history_df"].copy()
        hist_df["Max |dV|"] = hist_df["Max |dV|"].round(10)
        hist_df["Max mismatch"] = hist_df["Max mismatch"].round(10)
        st.dataframe(hist_df, use_container_width=True)

        st.subheader("Y-bus Matrix")
        y_bus = out["y_bus"]
        y_df = pd.DataFrame(
            [[f"{y.real:.5f} + j{y.imag:.5f}" for y in row] for row in y_bus],
            index=[f"Bus {i+1}" for i in range(n_buses)],
            columns=[f"Bus {i+1}" for i in range(n_buses)],
        )
        st.dataframe(y_df, use_container_width=True)
