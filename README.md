# planetary_parade

Counts the number of planets above the horizon (0º altitude) and above the treeline (10º altitude) at sunrise, sunset
as well as dawn and dusk (30 minutes before or after sunrise/sunset) to answer the question:

"when was the last time all 7 planets were above the horizon? and when will it happen again"

Also answers the question for visible planets (minus Uranus and Neptune) and with the Moon in the mix as well.

Created to support an article on WRAL.com [Look up for Saturn and Mercury to join the planetary parade this week
](https://www.wral.com/21882173/)

Change the t0, t1 dates to broaden or narrow the search. This is doing a lot of calculations (sunrise and sunset for each day as well 
the position of each of the 7 planets plus the moon at sunrise, sunset, as well as 30 minutes before and after those times)

You may also wnat to change the coordinates from Raleigh to your location.

Requires:
* Skyfield
* Pandas
* pytz
* JPL Planetary Ephemeris DE421 (automatically downloaded by Skyfield)