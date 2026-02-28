import streamlit as st
import pandas as pd

st.set_page_config(page_title="Learning Planner", layout="wide")
st.title("Python Web Development Learning Planner")

st.markdown("This tool displays a suggested schedule and resources based on your chosen focus area.")

focus = st.selectbox("Select your learning focus", ["Web Development (Flask/Django)", "Data Science (NumPy/Pandas)", "General Python"]) 

# static plan data
plan = {
    "Web Development (Flask/Django)": [
        ("Week 1", "Python basics, environment setup", "Real Python, official docs"),
        ("Week 2", "HTML/CSS/JS fundamentals", "MDN Web Docs, FreeCodeCamp"),
        ("Week 3", "Flask intro and to-do app", "Flask quickstart, Flask Mega-Tutorial"),
        ("Week 4", "Flask feature expansion", "Flask docs, Bootstrap"),
        ("Week 5", "Django basics (Polls tutorial)", "Django official tutorial"),
        ("Week 6", "Django intermediate features", "Django docs"),
        ("Weeks 7-8", "Portfolio project", "Choose a meaningful idea"),
    ],
    "Data Science (NumPy/Pandas)": [
        ("Week 1", "NumPy arrays & operations", "NumPy docs, Real Python"),
        ("Week 2", "pandas DataFrames", "pandas docs, tutorials"),
        ("Week 3", "Data cleaning & visualization", "Seaborn, Matplotlib guides"),
        ("Week 4", "Mini data projects", "Kaggle datasets"),
    ],
    "General Python": [
        ("Week 1", "Python syntax & data structures", "Official tutorial"),
        ("Week 2", "Modules, packages, virtualenv", "Real Python"),
        ("Week 3", "OOP & testing", "PyTest tutorial"),
        ("Week 4", "Small personal project", "Your own idea"),
    ],
}

resources = {
    "Web Development (Flask/Django)": [
        "Flask tutorial: https://flask.palletsprojects.com/en/latest/tutorial/",
        "Flask Mega-Tutorial by Miguel Grinberg",
        "Django tutorial: https://docs.djangoproject.com/en/stable/intro/tutorial01/",
        "MDN Web Docs for HTML/CSS/JS",
        "Heroku/PythonAnywhere deployment guides",
    ],
    "Data Science (NumPy/Pandas)": [
        "NumPy documentation",
        "pandas documentation",
        "Real Python data science tutorials",
        "Kaggle for datasets",
    ],
    "General Python": [
        "Official Python tutorial",
        "Real Python articles",
        "Python Crash Course book",
    ],
}

if focus:
    st.header("Suggested Schedule")
    schedule_df = pd.DataFrame(plan[focus], columns=["Timeframe", "Focus", "Resources"])
    st.table(schedule_df)

    st.header("Key Resources")
    for r in resources[focus]:
        st.write(f"- {r}")

    st.markdown("---")
    st.write("You can adapt the weeks to your pace. Happy learning!")
