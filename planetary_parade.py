from skyfield import api, almanac
from tqdm import tqdm
import pickle
import pandas as pd
from skyfield.api import N, W, wgs84
import datetime
from pprint import pprint
from pytz import timezone

eastern = timezone('US/Eastern')
ts = api.load.timescale()
load = api.Loader('/var/data')
# eph = api.load('de421.bsp')
eph = api.load('de423.bsp')
earth = eph['earth']
mars = eph['mars']
pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.max_rows', None)  # Show all columns
pd.set_option('display.width', 1000)  # Set wide display width
format_date = '%Y%m%d'
format_time = '%H:%M:%S'
treeline_degrees = 10

visible_planet_list = ['Mercury', 'Venus', 'Mars', 'Jupiter Barycenter', 'Saturn Barycenter']
visible_planet_list_short = [s.replace(' Barycenter', "") for s in visible_planet_list]
telescopic_planet_list = ['Uranus Barycenter', 'Neptune Barycenter']
telescopic_planet_list_short = [s.replace(' Barycenter', "") for s in telescopic_planet_list]
body_list = visible_planet_list + telescopic_planet_list + ['Moon']


def find_contiguous_date_ranges(dates):
    dates = sorted(set(dates))
    ranges = []
    start = dates[0]
    prev = dates[0]
    for current in dates[1:]:
        if current - prev > datetime.timedelta(days=1):  # Break in continuity
            ranges.append((start, prev))
            start = current
        prev = current
    ranges.append((start, prev))  # Add the last range
    return ranges


def build_dataframe(elevation_m, lat, lon, dusk_minutes, t0, t1):
    filename_dataframe = f'dataframe_{t0.utc_jpl()}_{t1.utc_jpl()}.pickle'
    events = ['morning', 'evening', 'sunrise', 'sunset']

    try:
        with open(filename_dataframe, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        raleigh_topo = wgs84.latlon(lat, lon, elevation_m=elevation_m)
        raleigh_vector_sum = earth + raleigh_topo
        data = {}

        # find sunrise/set, points one hour before sunrise and after sunset
        print(f"finding sunrises and sets for {t0.utc_jpl()} to {t1.utc_jpl()} at {lat:.2}, {lon:.2}")
        t, y = almanac.find_discrete(t0 - 1, t1 + 1, almanac.sunrise_sunset(eph, raleigh_topo))
        print(f"finding local dawn/dusk")
        for ti, yi in tqdm(zip(t, y), desc="sunrise/set"):
            calculate_sunriseset_dawndusk(data, dusk_minutes, ti, yi)

        # first and last dates are missing sunrise and sunset because of the timzone offset, remove them to prevent errors
        for day, v in tqdm(data.items()):
            for event in events:
                dt = data[day][f'{event}_dt']
                t = ts.from_datetime(dt)
                for body in body_list:
                    calculate_altitude(body, data, day, event, raleigh_vector_sum, t)

        while min(data.keys()) < t0.tt_strftime(format_date):
            del (data[min(data.keys())])
        while max(data.keys()) > t1.tt_strftime(format_date):
            del (data[max(data.keys())])
        with open(filename_dataframe, 'wb') as f:
            pickle.dump(data, f)
    df = pd.DataFrame.from_dict(data, orient='index')
    return df, events


def calculate_altitude(body, data, day, event, raleigh_vector_sum, t):
    planet = body.replace(' Barycenter', '')
    astro = raleigh_vector_sum.at(t).observe(eph[body])
    alt, az, distance = astro.apparent().altaz()
    data[day][f"{planet}_{event}_alt"] = alt.degrees


def calculate_planet_riseset(data, planet, t_rise, t_set):
    dt_rise = t_rise.astimezone(eastern)
    data[dt_rise.strftime(format_date)][f'{planet}_rise'] = dt_rise.strftime(format_time)
    dt_set = t_set.astimezone(eastern)
    data[dt_set.strftime(format_date)][f'{planet}_set'] = dt_set.strftime(format_time)


def calculate_sunriseset_dawndusk(data, dusk_minutes, ti, yi):
    dt = ti.astimezone(eastern)
    day = dt.strftime(format_date)
    riseset = 'rise' if yi else 'set'
    if day not in data:
        data[day] = {'sunrise_dt': None, 'sunset_dt': None}
    data[day][f"sun{riseset}_dt"] = dt
    if riseset == 'rise':
        data[day]['morning_dt'] = dt - datetime.timedelta(minutes=dusk_minutes)
    elif riseset == 'set':
        data[day]['evening_dt'] = dt + datetime.timedelta(minutes=dusk_minutes)


def main(start_year=1800, end_year=2199, dusk_minutes=30, lat=32.27, lon=-79.94, elevation_m=100):
    t0 = ts.utc(start_year, 1, 1, )  # subtract one from end year to ensure sunrise on Jan 1 is caught
    t1 = ts.utc(end_year + 1, 1, 1)  # add one to start year to ensure sunset on Dec 31 is caught

    df, events = build_dataframe(elevation_m, lat, lon, dusk_minutes, t0, t1)
    # df = df.loc['20400101':'20401231']

    # break big dataframe apart by time of day (sunrise/set, morning/evening) as well as
    # groupings of bodys (all, just planets, just visible planets and the moon, just visible planets)
    df_filter_planets = {}
    df_moon = {}
    df_visible = {}
    df_telescopic = {}

    df_final = None
    for event in events:
        df_just_altitude_columns = df[
            [s for s in df.columns if event in s and s != f"{event}_dt"]].copy()  # retain only altitude columns

        columns = [f'{s}_{event}_alt' "" for s in visible_planet_list_short]
        df_visible[event] = df_just_altitude_columns[columns]

        columns = [f'{s}_{event}_alt' "" for s in telescopic_planet_list_short]
        df_telescopic[event] = df_just_altitude_columns[columns]

        df_moon[event] = pd.DataFrame(df_just_altitude_columns[f'Moon_{event}_alt'])

        for d, name in zip([df_visible, df_telescopic, df_moon], ['visible', 'telescopic', 'Moon']):
            for attr_short, alt in zip(['above_horizon', 'above_treeline'], [0, treeline_degrees]):
                attr = f"{name}_{event}_{attr_short}"
                df_this_event = d[event]
                df_this_event[attr] = (df_this_event > alt).sum(axis=1)
                if df_final is None:
                    df_final = pd.DataFrame(df_this_event[attr])
                else:
                    df_final[attr] = df_this_event[attr]
    return df_final


if __name__ == '__main__':
    filename='planetary_parade.pickle'
    try:
        with open(filename, 'rb') as f:
            df = pickle.load(f)
    except Exception as e:
        df = main()
        with open(filename, 'wb') as f:
            pickle.dump(df, f)
    print(df.shape)
