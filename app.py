from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord, AltAz
from astropy.time import Time
import astropy.units as u

app = Flask(__name__)
CORS(app)

target_name = 'Sgr A*'
SGR_A = SkyCoord.from_name(target_name)
h_meters = 3.0
freq_hz = 20.1e6
c = 3.0e8

@app.route('/api/track', methods=['POST'])
def track_blackhole():
    data = request.json
    lat = float(data.get('lat', 0))
    lon = float(data.get('lon', 0))
    date_str = data.get('date')

    location = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
    
    # 1. Wire Orientation Optimization
    times_utc = Time(f"{date_str} 00:00:00", scale='utc') + np.arange(0, 24 * 60, 5) * u.minute
    altaz_utc = SGR_A.transform_to(AltAz(obstime=times_utc, location=location))

    visible_mask = altaz_utc.alt.deg > 0
    sgr_az_rad = altaz_utc.az.rad[visible_mask]
    sgr_elev_rad = altaz_utc.alt.rad[visible_mask]

    h_over_lambda = h_meters / (c / freq_hz)
    ground_factor = np.abs(np.sin(2 * np.pi * h_over_lambda * np.sin(sgr_elev_rad)))

    best_score = -1.0
    best_w1_angle = 0

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

    # 2. 24-Hour Orbital Curve
    times_plot_utc = Time(f"{date_str} 00:00:00", scale='utc') + np.arange(0, 24 * 60, 1) * u.minute
    altaz_plot = SGR_A.transform_to(AltAz(obstime=times_plot_utc, location=location))
    
    altitudes = altaz_plot.alt.deg.tolist()
    azimuths = altaz_plot.az.deg.tolist()
    time_labels = [t.to_datetime().strftime('%H:%M') for t in times_plot_utc]

    max_alt_idx = int(np.argmax(altitudes))

    return jsonify({
        "best_wire1_deg": best_w1_angle,
        "best_wire2_deg": best_w1_angle + 90,
        "peak_time": time_labels[max_alt_idx],
        "peak_altitude": round(altitudes[max_alt_idx], 2),
        "times": time_labels,
        "altitudes": altitudes,
        "azimuths": azimuths
    })

if __name__ == '__main__':
    app.run(port=5000)