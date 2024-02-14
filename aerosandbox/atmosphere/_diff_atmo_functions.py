import aerosandbox.numpy as np
from pathlib import Path
from aerosandbox.modeling.interpolation import InterpolatedModel
from aerosandbox.atmosphere._isa_atmo_functions import pressure_isa, temperature_isa, isa_base_altitude

# Define the altitudes of knot points

altitude_knot_points = np.array(
    [
        0,
        5e3,
        10e3,
      
    ] +
    list(0 + np.geomspace(1e3, 15e3, 11)) +
    list(10e3 - np.geomspace(1e3, 15e3, 11))
)

altitude_knot_points = np.sort(np.unique(altitude_knot_points))
print('altitude knot points =',altitude_knot_points)
temperature_knot_points = temperature_isa(altitude_knot_points)
pressure_knot_points = pressure_isa(altitude_knot_points)

# creates interpolated model for temperature and pressure
interpolated_temperature = InterpolatedModel(
    x_data_coordinates=altitude_knot_points,
    y_data_structured=temperature_knot_points,
)
interpolated_pressure = InterpolatedModel(
    x_data_coordinates=altitude_knot_points,
    y_data_structured=pressure_knot_points,
)


def pressure_differentiable(altitude):
    """
    Computes the pressure at a given altitude with a differentiable model.

    Args:
        altitude: Geopotential altitude [m]

    Returns: Pressure [Pa]

    """
    return interpolated_pressure(altitude)


def temperature_differentiable(altitude):
    """
    Computes the temperature at a given altitude with a differentiable model.

    Args:
        altitude: Geopotential altitude [m]

    Returns: Temperature [K]

    """
    return interpolated_temperature(altitude)
