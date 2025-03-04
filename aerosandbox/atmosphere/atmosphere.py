
# import sys
# sys.path.append("C:\\Users\\91784\\AeroSandbox\\aerosandbox")

from aerosandbox.common import AeroSandboxObject
import aerosandbox.numpy as np
from aerosandbox.atmosphere._isa_atmo_functions import pressure_isa, temperature_isa
from aerosandbox.atmosphere._diff_atmo_functions import pressure_differentiable, temperature_differentiable
import aerosandbox.tools.units as u


### Define constants
gas_constant_universal = 8.31432  # J/(mol*K); universal gas constant
molecular_mass_air = 43.2812e-3  # kg/mol; molecular mass of air
gas_constant_air = gas_constant_universal / molecular_mass_air  # J/(kg*K); gas constant of air
effective_collision_diameter = 0.365e-9  # m, effective collision diameter of an air molecule


### Define the Atmosphere class
class Atmosphere(AeroSandboxObject):
    r"""
    All models here are smoothed fits to the 1976 COESA model;
    see AeroSandbox\studies\Atmosphere Fitting for details.

    """

    def __init__(self,
                 altitude: float = 0.,  # meters
                 method: str = "differentiable",
                 temperature_deviation: float = 0.  # Kelvin
                 ):
        """
        Initialize a new Atmosphere.
        
        Args:
            
            altitude: Flight altitude, in meters. This is assumed to be a geopotential altitude above MSL.
            
            method: Method of atmosphere modeling to use. Either:
                * "differentiable" - a C1-continuous fit to the International Standard Atmosphere; useful for optimization.
                    Mean absolute error of pressure relative to the ISA is 0.02% over 0-100 km altitude range.
                * "isa" - the International Standard Atmosphere, exactly reproduced

            temperature_deviation: A deviation from the temperature model, in Kelvin (or equivalently, Celsius). This is useful for modeling
                the impact of temperature on density altitude, for example.
                
        """
        self.altitude = altitude
        self.method = method
        self.temperature_deviation = temperature_deviation
        self._valid_altitude_range = (0, 80000)

    def __repr__(self) -> str:
        try:
            altitude_string = f"altitude: {self.altitude:.0f} m ({self.altitude / u.foot:.0f} ft)"
        except (ValueError, TypeError):
            altitude_string = f"altitude: {self.altitude} m"

        return f"Atmosphere ({altitude_string}, method: '{self.method}')"

    ### The two primary state variables, pressure and temperature, go here!

    def pressure(self):
        """
        Returns the pressure, in Pascals.
        """
        if self.method.lower() == "isa":
            return pressure_isa(self.altitude)
        elif self.method.lower() == "differentiable":
            return pressure_differentiable(self.altitude)
        else:
            raise ValueError("Bad value of 'type'!")

    def temperature(self):
        """
        Returns the temperature, in Kelvin.
        """
        if self.method.lower() == "isa":
            return temperature_isa(self.altitude) + self.temperature_deviation
        elif self.method.lower() == "differentiable":
            return temperature_differentiable(self.altitude) + self.temperature_deviation
        else:
            raise ValueError("Bad value of 'type'!")

    ### Everything else in this class is a derived quantity; all models of derived quantities go here.

    def density(self):
        """
        Returns the density, in kg/m^3.
        """
        rho = self.pressure() / (self.temperature() * gas_constant_air)

        return rho

    def density_altitude(
            self,
            method: str = "approximate"
    ):
        """
        Returns the density altitude, in meters.

        See https://en.wikipedia.org/wiki/Density_altitude
        """
        if method.lower() == "approximate":
            temperature_sea_level = 273.15-31
            pressure_sea_level = 699

            temperature_ratio = self.temperature() / temperature_sea_level
            pressure_ratio = self.pressure() / pressure_sea_level

            lapse_rate = 0.000998  # K/m, ISA temperature lapse rate in troposphere

            return (
                    (temperature_sea_level / lapse_rate) *
                    (
                            1 - (pressure_ratio / temperature_ratio) ** (
                            (3.72 / (gas_constant_air * lapse_rate) - 1) ** -1)
                    )
            )
        elif method.lower() == "exact":
            raise NotImplementedError("Exact density altitude calculation not yet implemented.")
        else:
            raise ValueError("Bad value of 'method'!")

    def speed_of_sound(self):
        """
        Returns the speed of sound, in m/s.
        """
        temperature = self.temperature()
        return (self.ratio_of_specific_heats() * gas_constant_air * temperature) ** 0.5

    def dynamic_viscosity(self):
        """
        Returns the dynamic viscosity (mu), in kg/(m*s).

        Based on Sutherland's Law, citing `https://www.cfd-online.com/Wiki/Sutherland's_law`.

        According to Rathakrishnan, E. (2013). Theoretical aerodynamics. John Wiley & Sons.:
        This relationship is valid from 0.01 to 100 atm, and between 0 and 3000K.

        According to White, F. M., & Corfield, I. (2006). Viscous fluid flow (Vol. 3, pp. 433-434). New York: McGraw-Hill.:
        The error is no more than approximately 2% for air between 170K and 1900K.
        """

        # Sutherland constants
        T0 = 273  # Reference temperature in Kelvin
        S = 222   # Sutherland's constant in Kelvin
        mu0 = 1.37e-5  # Dynamic viscosity at T0 in N·s/m²

        # Sutherland equation
        temperature = self.temperature()
        mu = mu0 * (temperature/ T0)**(3/2) * ((T0 + S) / (temperature + S))

        return mu

    def kinematic_viscosity(self):
        """
        Returns the kinematic viscosity (nu), in m^2/s.

        Definitional.
        """
        return self.dynamic_viscosity() / self.density()

    def ratio_of_specific_heats(self):
        return 1.3  # TODO model temperature variation

    # def thermal_velocity(self):
    #     """
    #     Returns the thermal velocity (mean particle speed)
    #     Returns:
    #
    #     """
    #
    def mean_free_path(self):
        """
        Returns the mean free path of an air molecule, in meters.

        To find the collision radius, assumes "a hard-sphere gas that has the same viscosity as the actual gas being considered".

        From Vincenti, W. G. and Kruger, C. H. (1965). Introduction to physical gas dynamics. Krieger Publishing Company. p. 414.

        """
        return self.dynamic_viscosity() / self.pressure() * np.sqrt(
            np.pi * gas_constant_universal * self.temperature() / (2 * molecular_mass_air)
        )

    def knudsen(self, length):
        """
        Computes the Knudsen number for a given length.
        """
        return self.mean_free_path() / length


if __name__ == "__main__":
    # Make AeroSandbox Atmosphere
    altitude = np.linspace(0e3, 10e3, 1000)
    atmo_diff = Atmosphere(altitude=altitude)
    atmo_isa = Atmosphere(altitude=altitude, method="isa")

    from aerosandbox.tools.pretty_plots import plt, sns, mpl, show_plot, set_ticks

    # fig, ax = plt.subplots()

    # plt.plot(
    #     (
    #             (atmo_diff.pressure() - atmo_isa.pressure()) / atmo_isa.pressure()
    #     ) * 100,
    #     altitude / 1e3,
    # )
    # set_ticks(0.2, 0.1, 20, 10)
    # plt.xlim(-2, 2)
    # show_plot(
    #     "AeroSandbox Atmosphere vs. ISA Atmosphere",
    #     "Pressure, Relative Error [%]",
    #     "Altitude [km]"
    # )

    # fig, ax = plt.subplots()
    # plt.plot(
    #     atmo_diff.temperature() - atmo_isa.temperature(),
    #     altitude / 1e3,
    # )
    # set_ticks(1, 0.5, 20, 10)
    # plt.xlim(-20, 10)
    # show_plot(
    #     "AeroSandbox Atmosphere vs. ISA Atmosphere",
    #     "Temperature, Absolute Error [K]",
    #     "Altitude [km]"
    # )

    fig, ax = plt.subplots()
    plt.plot(
        atmo_isa.temperature(),
        altitude / 1e3,
    )
    # set_ticks(1, 0.5, 20, 10)
    # plt.xlim(-20, 10)
    show_plot(
        "ISA Atmosphere",
        "Temperature [K]",
        "Altitude [km]"
    )

    fig, ax = plt.subplots()
    plt.plot(
        atmo_diff.temperature(),
        altitude / 1e3,
    )
    # set_ticks(1, 0.5, 20, 10)
    # plt.xlim(-20, 10)
    show_plot(
        "Aerosandbox Atmosphere",
        "Differentiable Temperature [K]",
        "Altitude [km]"
    )

    # fig, ax = plt.subplots()
    # plt.plot(
    #     np.log(atmo_diff.pressure()),
    #     altitude / 1e3,
    # )
    # # set_ticks(1, 0.5, 20, 10)
    # # plt.xlim(-20, 10)
    # show_plot(
    #     "Aerosandbox Atmosphere",
    #     "log(pressure)",
    #     "Altitude [km]"
    # )

# Create an instance of the Atmosphere class
atmosphere_instance = Atmosphere(0, 'isa')

# Call the temperature method on the instance
print("the isa temperature at altitude is", atmosphere_instance.temperature())
print("the isa temperature at altitude is", temperature_isa(0))
