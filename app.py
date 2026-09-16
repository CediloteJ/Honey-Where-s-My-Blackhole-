import io
import base64
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Prevents GUI crashes on cloud servers
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from astropy.coordinates import EarthLocation, SkyCoord, AltAz
from astropy.time import Time
import astropy.units as u

app = Flask(__name__)
CORS(app)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Honey, where's my black hole?</title>
    <style>
        body { font-family: monospace; background: #0b0e14; color: #e1e6ed; padding: 20px; text-align: center; }
        .card { background: #161b22; padding: 20px; border-radius: 8px; margin: 15px auto; max-width: 800px; border: 1px solid #30363d; }
        button { background: #238636; color: white; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; }
        input { padding: 8px; border-radius: 4px; border: 1px solid #30363d; background: #0d1117; color: white; margin: 5px; }
        img { max-width: 100%; height: auto; border-radius: 8px; margin-top: 15px; }
    </style>
</head>
<body>

    <h1>🕳️ Honey, where's my black hole?</h1>
    <p>Sagittarius A* Tracking & Crossed-Dipole Optimization</p>

    <div class="card">
        <label>Date & Time (UTC): </label>
        <input type="text" id="obsDate" value="2026-09-15 18:00:00">
        <br>
        <label>Lat: </label><input type="text" id="lat" style="width: 80px;">
        <label>Lon: </label><input type="text" id="lon" style="width: 80px;">
        <br><br>
        <button onclick="runScript()">Run Sky Tracking Script</button>
        <p id="status" style="color: #8b949e;"></p>
    </div>

    <div class="card" id="resultsCard" style="display:none;">
        <pre id="outputConsole" style="text-align: left; background: #000; padding: 15px; border-radius: 5px; color: #00ff00;"></pre>
        <h3>Polar Sky Track</h3>
        <img id="polarPlot" src="" />
        <h3>Altitude vs Time</h3>
        <img id="altPlot" src="" />
    </div>

    <script>
        // Get user position via browser GPS
        window.onload = function() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition((pos) => {
                    document.getElementById('lat').value = pos.coords.latitude.toFixed(2);
                    document.getElementById('lon').value = pos.coords.longitude.toFixed(2);
                });
            }
        };

        async function runScript() {
            const dateVal = document.getElementById('obsDate').value;
            const latVal = document.getElementById('lat').value || 34.19;
            const lonVal = document.getElementById('lon').value || -79.76;

            document.getElementById('status').innerText = "Running calculations...";

            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date: dateVal, lat: latVal, lon: lonVal })
            });

            const data = await response.json();

            document.getElementById('outputConsole').innerText = data.console_text;
            document.getElementById('polarPlot').src = "data:image/png;base64," + data.polar_img;
            document.getElementById('altPlot').src = "data:image/png;base64," + data.alt_img;
            
            document.getElementById('resultsCard').style.display = "block";
            document.getElementById('status').innerText = "Done!";
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def home():
    return render_template_string(HTML_PAGE)

@app.route('/api/run', methods=['POST'])
def run_user_script():
    data = request.json
    date_str = data.get('date', '2026-09-15 18:00:00')
    lat = float(data.get('lat', 34.19))
    lon = float(data.get('lon', -79.76))

    target_name = 'Sgr A*'
    h_meters = 3.0       
    freq_hz = 20.1e6     
    c = 3.0e8            

    location = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
    target = SkyCoord.from_name(target_name)

    # --- YOUR ORIGINAL OPTIMIZATION LOOP ---
    times_utc = Time(date_str, scale='utc') + np.arange(0, 24 * 60, 5) * u.minute
    altaz_utc = target.transform_to(AltAz(obstime=times_utc, location=location))

    visible_mask = altaz_utc.alt.deg > 0
    sgr_az_rad = altaz_utc.az.rad[visible_mask]
    sgr_elev_rad = altaz_utc.alt.rad[visible_mask]

    h_over_lambda = h_meters / (c / freq_hz)
    ground_factor = np.abs(np.sin(2 * np.pi * h_over_lambda * np.sin(sgr_elev_rad)))

    best_score = -1.0
    best_w1_angle = 0
    best_w2_angle = 90

    if len(sgr_elev_rad) > 0:
        for w1_deg in range(0, 95, 5):
            w1_rad = np.radians(w1_deg)
            w2_rad = np.radians(w1_deg + 90)
            
            dot1 = np.cos(sgr_elev_rad) * np.cos(sgr_az_rad - w1_rad)
            gain_w1 = np.sqrt(np.maximum(0, 1 - dot1**2))
            
            dot2 = np.cos(sgr_elev_rad) * np.cos(sgr_az_rad - w2_rad)
            gain_w2 = np.sqrt(np.maximum(0, 1 - dot2**2))
            
            total_gain = np.sqrt(gain_w1**2 + gain_w2**2) * ground_factor
            score = np.sum(total_gain)
            
            if score > best_score:
                best_score = score
                best_w1_angle = w1_deg
                best_w2_angle = w1_deg + 90

    # --- YOUR ORIGINAL 24HR TRACK ---
    duration_hours = 24
    start_time_utc = Time(date_str, scale='utc')
    times_plot_utc = start_time_utc + np.arange(0, duration_hours * 60, 1) * u.minute

    altaz_plot = target.transform_to(AltAz(obstime=times_plot_utc, location=location))
    alt = altaz_plot.alt.deg
    az = altaz_plot.az.rad
    r = 90 - alt

    dt_list_local = np.array([t.to_datetime().astimezone() for t in times_plot_utc])
    local_tz_info = dt_list_local[0].tzinfo
    local_tz_name = dt_list_local[0].strftime('%Z')
    hourly_mask = np.array([dt.minute == 0 for dt in dt_list_local])

    # --- YOUR ORIGINAL POLAR PLOT ---
    fig1 = plt.figure(figsize=(7, 7), facecolor='black')
    ax1 = fig1.add_subplot(111, polar=True, facecolor='#001144')
    ax1.set_theta_zero_location('N')
    ax1.set_theta_direction(1)
    ax1.set_ylim(0, 90)
    ax1.set_yticks([30, 60, 90])
    ax1.set_yticklabels(['', '', ''])
    ax1.grid(color='#4466aa', linestyle='--', linewidth=0.8)
    ax1.set_xticks(np.radians([0, 90, 180, 270]))
    ax1.set_xticklabels(['N', 'E', 'S', 'W'], color='yellow', fontsize=12, fontweight='bold')

    r_plot = r.copy()
    r_plot[alt < 0] = np.nan
    ax1.plot(az, r_plot, color='#ff7700', lw=2)

    for i in np.where(hourly_mask & (alt >= 0))[0]:
        ax1.plot(az[i], r[i], 'o', color='yellow', markersize=4)
        ax1.annotate(dt_list_local[i].strftime('%H:%M'), xy=(az[i], r[i]), xytext=(0, 10), textcoords='offset points', ha='center', color='yellow', fontsize=9)

    plt.title(f"Sky Track for {target_name}\n({lat:.2f}°, {lon:.2f}°)", color='white', pad=15)
    plt.tight_layout()
    
    buf1 = io.BytesIO()
    plt.savefig(buf1, format='png', facecolor=fig1.get_facecolor())
    buf1.seek(0)
    polar_base64 = base64.b64encode(buf1.getvalue()).decode('utf-8')
    plt.close(fig1)

    # --- YOUR ORIGINAL ALTITUDE PLOT ---
    fig2 = plt.figure(figsize=(8, 4))
    plt.plot(dt_list_local, alt, color='navy', lw=2, label=f'{target_name}')
    plt.axhline(0, color='red', linestyle='--', label='Horizon')
    plt.fill_between(dt_list_local, alt, -90, where=(alt <= 0), color='gray', alpha=0.3, label='Below Horizon')

    for i in np.where(hourly_mask & (alt > 0))[0]:
        plt.annotate(dt_list_local[i].strftime('%H:%M'), (dt_list_local[i], alt[i]), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=8)

    ax_plt = plt.gca()
    ax_plt.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=local_tz_info))
    ax_plt.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz=local_tz_info))
    plt.gcf().autofmt_xdate()

    plt.title(f'{target_name} Altitude vs. Time ({local_tz_name})')
    plt.xlabel(f'Time ({local_tz_name})')
    plt.ylabel('Altitude (degrees)')
    plt.ylim(-90, max(max(alt) + 15, 25))
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='lower right')
    plt.tight_layout()

    buf2 = io.BytesIO()
    plt.savefig(buf2, format='png')
    buf2.seek(0)
    alt_base64 = base64.b64encode(buf2.getvalue()).decode('utf-8')
    plt.close(fig2)

    # --- YOUR CONSOLE TEXT ---
    max_alt_idx = np.argmax(alt)
    optimal_view_time_local = dt_list_local[max_alt_idx]
    max_altitude = alt[max_alt_idx]

    console_output = f"OPTIMAL WIRE ORIENTATION RESULTS FOR {target_name}\n"
    console_output += f"Observer Location : {lat:.2f}° N, {lon:.2f}° W\n"
    console_output += f"Target Max Alt    : {np.max(altaz_utc.alt.deg):.1f}° above horizon\n\n"
    console_output += f"BEST SETUP FOUND\n"
    console_output += f"Wire 1 Angle    : {best_w1_angle}° from North\n"
    console_output += f"Wire 2 Angle    : {best_w2_angle}° from North\n\n"
    console_output += f"Peak Viewing Time: {optimal_view_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
    console_output += f"Peak Altitude    : {max_altitude:.2f}°"

    return jsonify({
        "console_text": console_output,
        "polar_img": polar_base64,
        "alt_img": alt_base64
    })

if __name__ == '__main__':
    app.run(port=5000)
