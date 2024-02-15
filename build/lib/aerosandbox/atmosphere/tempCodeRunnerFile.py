
from aerosandbox.tools.pretty_plots import plt, sns, mpl, show_plot, set_ticks
altitude = np.linspace(0e3, 10e3, 1000)
atmo_isa = temperature_isa(altitude=altitude)
fig, ax = plt.subplots()
plt.plot(
    atmo_isa,
    altitude / 1e3,
)
    # set_ticks(1, 0.5, 20, 10)
    # plt.xlim(-20, 10)
show_plot(
    "ISA Atmosphere",
    "Temperature [K]",
    "Altitude [km]"
)