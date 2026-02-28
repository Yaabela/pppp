"""A simple script to explore NumPy and pandas with notifications.

Run this program to see basic array and DataFrame operations. It prints messages
("notifications") to the console when each step completes.
"""

import numpy as np
import pandas as pd
import logging

# configure logging to print to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def array_demo():
    logging.info("Starting NumPy array demo")
    # create a 1-D array
    a = np.arange(10)
    logging.info(f"Created array: {a}")
    # reshape into 2x5
    b = a.reshape((2, 5))
    logging.info(f"Reshaped array to 2x5:\n{b}")

    # compute statistics
    logging.info(f"Mean: {np.mean(a)}, Std: {np.std(a)}")
    logging.info("NumPy demo complete")


def dataframe_demo():
    logging.info("Starting pandas DataFrame demo")
    # create a simple DataFrame
    df = pd.DataFrame({
        "A": np.random.randn(5),
        "B": np.random.randint(0, 10, size=5),
    })
    logging.info(f"Initial DataFrame:\n{df}")

    # add a new column
    df["C"] = df["A"] * df["B"]
    logging.info(f"After adding column C:\n{df}")

    # basic filtering
    filtered = df[df["B"] > 5]
    logging.info(f"Rows where B > 5:\n{filtered}")
    logging.info("pandas demo complete")


def main():
    logging.info("Program started")
    array_demo()
    dataframe_demo()
    logging.info("All demos finished. You have been notified via console output.")


if __name__ == "__main__":
    main()