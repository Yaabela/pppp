import streamlit as st

# Simple Streamlit app that triggers a desktop notification using JS

st.set_page_config(page_title="Notifier Example")
st.title("Streamlit Desktop Notification Demo")
st.write("Click the button below to see a browser/desktop notification.")

# helper to send a notification via JavaScript

def send_desktop_notification(title: str, body: str):
    # The JavaScript Notification API requires permission from the user;
    # this snippet requests permission and then shows the notification.
    js = f"""
    <script>
    function notifyMe() {{
      if (!("Notification" in window)) {{
        alert("This browser does not support desktop notifications.");
      }}
      else if (Notification.permission === "granted") {{
        new Notification("{title}", {{body: "{body}"}});
      }}
      else if (Notification.permission !== "denied") {{
        Notification.requestPermission().then(function (permission) {{
          if (permission === "granted") {{
            new Notification("{title}", {{body: "{body}"}});
          }}
        }});
      }}
    }}
    notifyMe();
    </script>
    """
    st.components.v1.html(js, height=0, width=0)

if st.button("Run program and notify me"):
    # here you could run any Python logic; we'll simulate with a message
    st.write("Program logic executed — doing some work...")
    # notify user when done
    send_desktop_notification("Streamlit Notification", "Your program has finished running.")
    st.success("Notification sent (check your desktop/browser).")
