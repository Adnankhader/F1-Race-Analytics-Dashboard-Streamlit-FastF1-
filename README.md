# 🏁 F1 Race Analytics Dashboard (Streamlit + FastF1)

An interactive **Formula 1 race analytics dashboard** built using **Streamlit**, **FastF1**, and Python.
This app provides deep insights into driver performance, race pace, pit strategies, and comparative analysis.

---

## 🚀 Features

* 📊 **Driver Comparison Cards**

  * Grid position vs Finish position
  * Positions gained/lost
  * Points scored
  * Race status

* 🏎️ **Race Pace Analysis**

  * lap times
  * Clean lap filtering
  * Smooth visualization for true pace comparison

* ⛽ **Pit Stop Analysis**

  * Pit stop timing insights
  * Strategy comparison across drivers

* 📈 **Interactive Visualizations**

  * Clean and minimal UI
  * Matplotlib-based performance plots
  * Styled components with team colors

---

## 🧠 Tech Stack

* **Python**
* **Streamlit** – UI framework
* **FastF1** – F1 telemetry and timing data
* **Pandas & NumPy** – Data processing
* **Matplotlib** – Visualization

---

## 📂 Project Structure

```
f1-streamlit-dashboard/
│
├── app.py                 # Main Streamlit app
├── requirements.txt       # Dependencies
├── .streamlit/
│   └── config.toml        # Theme config (optional)
├── assets/                # Images / logos (optional)
└── cache/                 # FastF1 cache (auto-generated)
```

---

## ⚙️ Installation (Run Locally)

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/f1-streamlit-dashboard.git
cd f1-streamlit-dashboard
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run app.py
```

---

## 🌐 Deployment (Streamlit Cloud)

1. Push this project to GitHub
2. Go to Streamlit Community Cloud
3. Click **Deploy an App**
4. Select:

   * Repo: your repository
   * Branch: `main`
   * File: `app.py`
5. Click **Deploy**

---

## ⚠️ Important Notes

* FastF1 data is cached locally:

```python
fastf1.Cache.enable_cache('cache')
```

* First run may be slow due to data download
* Use caching (`@st.cache_data`) to improve performance

---

## 🧩 Future Improvements

* 🔴 Live telemetry comparison
* 📍 Track position visualization
* 🧮 Strategy prediction models
* 📊 Advanced driver metrics

---

## 🤝 Contributing

Feel free to fork this repo and improve it!
Pull requests are welcome.

---

## 📜 License

This project is for educational and personal use.

---

## 🙌 Acknowledgements

* FastF1 for incredible F1 data access
* Streamlit for rapid app development

---

## 💡 Author

Built with ❤️ by *Adnan Khader*
Aspiring Data Analyst & Business Analytics enthusiast
