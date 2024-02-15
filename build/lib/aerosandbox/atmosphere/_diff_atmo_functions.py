import aerosandbox.numpy as np
from pathlib import Path
from aerosandbox.modeling.interpolation import InterpolatedModel
from aerosandbox.atmosphere._isa_atmo_functions import pressure_isa, temperature_isa, isa_base_altitude


from aerosandbox.common import AeroSandboxObject

import aerosandbox.tools.units as u
# Define the altitudes of knot points

# altitude_knot_points = np.array(
#     [
#         0,
#         5e3,
#         10e3,
      
#     ] +
#     list(0 + np.geomspace(1e3, 12e3, 30)) +
#     list(10e3 - np.geomspace(1e3, 12e3, 30))
# )

# altitude_knot_points = np.sort(np.unique(altitude_knot_points))
altitude_knot_points = np.linspace(-5e3, 20e3, 100)
# print('altitude knot points =',altitude_knot_points)
temperature_knot_points = temperature_isa(altitude_knot_points)
pressure_knot_points = pressure_isa(altitude_knot_points)

# creates interpolated model for temperature and pressure
interpolated_temperature = InterpolatedModel(
    x_data_coordinates=altitude_knot_points,
    y_data_structured=temperature_knot_points,
)
interpolated_log_pressure = InterpolatedModel(
    x_data_coordinates=altitude_knot_points,
    y_data_structured=np.log(pressure_knot_points),
)


def pressure_differentiable(altitude):
    """
    Computes the pressure at a given altitude with a differentiable model.

    Args:
        altitude: Geopotential altitude [m]

    Returns: Pressure [Pa]

    """
    return interpolated_log_pressure(altitude)


def temperature_differentiable(altitude):
    """
    Computes the temperature at a given altitude with a differentiable model.

    Args:
        altitude: Geopotential altitude [m]

    Returns: Temperature [K]

    """
    return np.exp(interpolated_log_pressure(altitude))


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