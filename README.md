# 3D Earth Weather — Python-first weather dashboard

A learning project for a weather website with a liquid-glass interface, animated weather cards, a temperature chart, seven-day forecast, city search, and an interactive 3D Earth explorer.

**Main application code:** Python (`app.py`). Streamlit builds the UI, Python makes and caches weather/geocoding requests, and Plotly draws the temperature chart. A small JavaScript block embedded in `app.py` powers the interactive 3D globe through Globe.gl.

## Features

- Current conditions, feels-like temperature, humidity, wind, gusts, cloud cover, pressure, UV index, sunrise and sunset.
- 24-hour temperature line chart and upcoming hourly cards.
- Seven-day forecast with highs, lows and precipitation probability.
- Search for locations worldwide and switch between Celsius and Fahrenheit.
- Interactive 3D globe: drag to rotate, scroll to zoom, select city markers or click a coordinate to fetch weather.
- Temperature-tinted city markers when the multi-location weather request works.
- Glass-style UI, responsive layout, subtle entry animations and reduced-motion support.
- Open-Meteo requests cached for 15 minutes to reduce repeated calls.

## 1. Run locally on Windows

### Install prerequisites

1. Install Python 3.11 or 3.12 from [python.org](https://www.python.org/downloads/). During installation, tick **Add Python to PATH**.
2. Install [Visual Studio Code](https://code.visualstudio.com/).
3. Optional but recommended: install [Git](https://git-scm.com/downloads).

Open Command Prompt or VS Code's terminal and check Python:

```bash
python --version
```

On some Windows installations, use `py --version` instead.

### Extract and open the folder

Extract the ZIP. In VS Code choose **File → Open Folder**, then select `aurora-weather-python`.

### Create a virtual environment

In VS Code choose **Terminal → New Terminal**. Confirm the terminal is inside the project folder, then run:

```bash
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

### Install libraries and start the app

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

The terminal will show an address, usually `http://localhost:8501`. Open it in Chrome or another modern browser. Leave the terminal running while using the app; press `Ctrl+C` in the terminal to stop it.

<img width="1679" height="878" alt="Screenshot 2026-10-27 011457" src="https://github.com/user-attachments/assets/baf91005-80ef-411c-854a-8b7b73e9c91c" />




## 2. Add this project to GitHub (beginner-friendly)

### Create a repository on GitHub

1. Sign in at [github.com](https://github.com/).
2. Click the **+** button → **New repository**.
3. Name it `aurora-weather-python`.
4. Choose **Public** if you want others to see the code and deploy it easily, or **Private** if you prefer.
5. You can initialize it with a README, but since this project already has a README, leave **Add a README file** unchecked for the simplest first upload.
6. Click **Create repository**.

### Upload files using GitHub's website

1. Open the new, empty repository.
2. Choose **Add file → Upload files**.
3. Open the extracted `aurora-weather-python` folder on your computer.
4. Drag these files into the browser: `app.py`, `requirements.txt`, `README.md`, and `.gitignore`.
5. Enter a commit message such as `Add Python weather dashboard`.
6. Click **Commit changes**.

The repository must have `app.py` and `requirements.txt` at its root (the first level of the repository). Do not upload the `.venv` folder.

## 3. Alternative: upload with Git commands

Use this option if you installed Git. Open a terminal in the extracted project folder, then run:

```bash
git init
git add app.py requirements.txt README.md .gitignore
git commit -m "Add Aurora Weather app"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/aurora-weather-python.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username. If Git says the remote already exists, inspect it with `git remote -v`; do not add it twice. GitHub may ask you to sign in using a browser or credential manager. Do not put a GitHub password or personal access token in the code or README.

## 4. Publish it as a website with Streamlit Community Cloud

1. Push the project to GitHub using one of the methods above.
2. Visit [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
3. Choose **Create app**.
4. Select your repository `aurora-weather-python`, branch `main`, and main file path `app.py`.
5. Choose **Deploy**.
6. Wait for the build to finish. Streamlit will provide a public URL ending in `.streamlit.app`.

The app dependencies are in `requirements.txt`; Streamlit Community Cloud uses this file to install the packages. If deployment fails, open the app's logs and check for a missing dependency or Python error.

Official deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy

## How the code works

### `app.py`

The single Python file is organized into sections so you can learn it gradually:

1. **Constants** — API URLs, WMO weather-code descriptions and sample globe cities.
2. **Utility functions** — readable weather descriptions, temperature conversion and formatting.
3. **API functions** — `fetch_forecast()` requests weather data and `search_locations()` geocodes a city. `@st.cache_data` stores results temporarily.
4. **CSS** — controls the liquid-glass look, colors, responsive layout and animations.
5. **Dashboard renderer** — creates metric cards, hourly cards, a Plotly chart and seven-day forecast cards.
6. **3D globe renderer** — small browser-side JavaScript uses Globe.gl because WebGL globe rendering belongs in the browser. It calls the public weather endpoint when a city marker or globe coordinate is selected.
7. **`main()`** — sets up Streamlit's sidebar controls, stores the selected location in session state and chooses which page to render.

### Weather API

- Geocoding: `https://geocoding-api.open-meteo.com/v1/search`
- Forecast: `https://api.open-meteo.com/v1/forecast`

No API key is required for eligible non-commercial use of Open-Meteo's free endpoint. Read the current terms before using the project commercially or for an ad-supported site. Weather values are model forecasts/estimates; they are not a guarantee or a satellite image.

- API docs: https://open-meteo.com/en/docs
- Geocoding docs: https://open-meteo.com/en/docs/geocoding-api
- Terms: https://open-meteo.com/en/terms

### 3D globe

<img width="1679" height="865" alt="Screenshot 2026-10-27 011518" src="https://github.com/user-attachments/assets/7474f080-9f1c-4316-897f-15e71c06280c" />


Globe.gl and the Earth/night-sky textures load from public CDNs, so the browser needs an internet connection. The selected location's model conditions update in the panel embedded within the globe. It is not a continuous satellite or rain-radar feed. A true radar/cloud imagery layer would require an appropriate separate map-tile or weather-imagery provider.

## Troubleshooting

- **`python` is not recognized:** reinstall Python and enable **Add Python to PATH**, or use the Windows `py` launcher.
- **`pip` is not recognized:** use `python -m pip install -r requirements.txt`.
- **`streamlit` is not recognized:** activate `.venv` and run `python -m streamlit run app.py`.
- **Weather does not load:** check your internet connection; Open-Meteo must be reachable from the machine or hosted server.
- **Earth is blank:** allow scripts and texture assets from public CDNs; try refreshing. The dashboard still uses Python for its weather data even if the globe fails to load.
- **GitHub upload shows no app:** ensure `app.py` and `requirements.txt` sit in the repository root and Streamlit's main file is set to `app.py`.

## License

This project code is provided as a learning starter. Check the licenses and terms of Open-Meteo, Globe.gl, Plotly, Streamlit, the Earth textures and any images before redistributing or using commercially.
