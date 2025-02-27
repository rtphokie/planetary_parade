from skyfield import api, almanac
import pandas as pd
from skyfield.api import N, W, wgs84
import datetime
from pprint import pprint
from pytz import timezone

eastern = timezone('US/Eastern')
ts = api.load.timescale()
load = api.Loader('/var/data')
eph = api.load('de421.bsp')
earth = eph['earth']
mars = eph['mars']
pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.max_rows', None)  # Show all columns
pd.set_option('display.width', 1000)  # Set wide display width


def main(minutes=30):
    raleigh_topo = wgs84.latlon(37.2710 * N, 79.9414 * W, elevation_m=100)
    raleigh_vector_sum = earth + raleigh_topo

    t0 = ts.utc(2000, 1, 1)
    t1 = ts.utc(2051, 1, 1)
    data = {}
    visible_planet_list = ['Mercury', 'Venus', 'Mars', 'Jupiter Barycenter', 'Saturn Barycenter', 'Moon']
    planet_list = visible_planet_list + ['Uranus Barycenter', 'Neptune Barycenter']

    # find sunrise/set, points one hour before sunrise and after sunset
    t, y = almanac.find_discrete(t0, t1, almanac.sunrise_sunset(eph, raleigh_topo))
    for ti, yi in zip(t, y):
        calculate_sunriseset_dawndusk(data, minutes, ti, yi)

    for body in planet_list:
        planet = body.replace(' Barycenter', '')
        t_risings, _ = almanac.find_risings(raleigh_vector_sum, eph[body], t0, t1)
        t_settings, _ = almanac.find_settings(raleigh_vector_sum, eph[body], t0, t1)
        for t_rise, t_set in zip(t_risings, t_settings):
            calculate_planet_riseset(data, planet, t_rise, t_set)

    # first and last dates are missing sunrise and sunset because of the timzone offset, remove them to prevent errors
    del (data[min(data.keys())])
    del (data[max(data.keys())])
    events = ['morning', 'evening', 'sunrise', 'sunset']
    for day, v in data.items():
        for event in events:
            dt = data[day][f'{event}_dt']
            t = ts.from_datetime(dt)
            for body in planet_list:
                calculate_altitude(body, data, day, event, raleigh_vector_sum, t)

    df = pd.DataFrame.from_dict(data, orient='index')

    # create bunches of dataframes to slice and dice this data by time of day (sunrise/set, morning/evening) and
    # groupings of bodys (all, just planets, just visible planets and the moon, just visible planets)
    df_filter_all = {}
    df_filter_planets = {}
    df_filter_visible_plnaets = {}
    df_filter_visible_plnaets_plus_moon = {}
    for event in events:
        df_just_altitude_columns = df[
            [s for s in df.columns if event in s and s != f"{event}_dt"]]  # retain only altitude columns
        df_filter_all[event] = df_just_altitude_columns
        df_filter_planets[event] = df_just_altitude_columns.drop(columns=[f'Moon_{event}_alt'])  # just planets
        df_filter_visible_plnaets_plus_moon[event] = df_just_altitude_columns.drop(
            columns=[f'Uranus_{event}_alt', f'Neptune_{event}_alt'])  # just visible planets and the moon
        df_filter_visible_plnaets[event] = df_just_altitude_columns.drop(
            columns=[f'Uranus_{event}_alt', f'Neptune_{event}_alt', f'Moon_{event}_alt'])  # just visible planets

        for d in [df_filter_all, df_filter_planets, df_filter_visible_plnaets, df_filter_visible_plnaets_plus_moon]:
            for attr, alt in zip(['above_horizon', 'above_treeline'], [0, 10]):
                d[event][attr] = (d[event] > alt).sum(axis=1)

    df1 = df_filter_visible_plnaets['evening']
    print("days with all 7 planets above horizon in the evening")
    print(df1[df1.above_horizon >= 7])
    print("days with all 5 visible planets above horizon in the evening")
    print(df1[df1.above_treeline >= 5])


def calculate_altitude(body, data, day, event, raleigh_vector_sum, t):
    planet = body.replace(' Barycenter', '')
    astro = raleigh_vector_sum.at(t).observe(eph[body])
    alt, az, distance = astro.apparent().altaz()
    data[day][f"{planet}_{event}_alt"] = alt.degrees


def calculate_planet_riseset(data, planet, t_rise, t_set):
    dt_rise = t_rise.astimezone(eastern)
    data[dt_rise.strftime('%Y%m%d')][f'{planet}_rise'] = dt_rise.strftime('%H:%M:%S')
    dt_set = t_set.astimezone(eastern)
    data[dt_set.strftime('%Y%m%d')][f'{planet}_set'] = dt_set.strftime('%H:%M:%S')


def calculate_sunriseset_dawndusk(data, minutes, ti, yi):
    dt = ti.astimezone(eastern)
    day = dt.strftime('%Y%m%d')
    riseset = 'rise' if yi else 'set'
    if day not in data:
        data[day] = {'sunrise_dt': None, 'sunset_dt': None}
    data[day][f"sun{riseset}_dt"] = dt
    if riseset == 'rise':
        data[day]['morning_dt'] = dt - datetime.timedelta(minutes=minutes)
    elif riseset == 'set':
        data[day]['evening_dt'] = dt + datetime.timedelta(minutes=minutes)


if __name__ == '__main__':
    main()