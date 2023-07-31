import aerosandbox.numpy as np
from aerosandbox.geometry.airfoil.airfoil import Airfoil
from aerosandbox.geometry.airfoil.airfoil_families import get_kulfan_coordinates, get_kulfan_parameters
from aerosandbox.modeling.splines.hermite import linear_hermite_patch, cubic_hermite_patch
from typing import Union, Dict, List


class KulfanAirfoil(Airfoil):
    def __init__(self,
                 name: str = "Untitled",
                 lower_weights: np.ndarray = None,
                 upper_weights: np.ndarray = None,
                 leading_edge_weight: float = 0.,
                 TE_thickness: float = 0.,
                 N1: float = 0.5,
                 N2: float = 1.0,
                 ):
        ### Handle the airfoil name
        self.name = name

        ### Check to see if the airfoil is a "known" airfoil, based on its name.
        try:
            coordinate_airfoil = Airfoil(name)
        except UserWarning:
            pass

        if (
                lower_weights is None and
                upper_weights is None
        ):  # Try to fall back on parameters from the coordinate airfoil, if it's something from the UIUC database
            try:
                coordinate_airfoil = Airfoil(name)
                if coordinate_airfoil.coordinates is None:
                    raise UserWarning

                parameters = get_kulfan_parameters(
                    coordinates=coordinate_airfoil.coordinates,
                    n_weights_per_side=8,
                    N1=N1,
                    N2=N2,
                    normalize_coordinates=True,
                    use_leading_edge_modification=True,
                )

                lower_weights = parameters["lower_weights"]
                upper_weights = parameters["upper_weights"]
                leading_edge_weight = parameters["leading_edge_weight"]
                TE_thickness = parameters["TE_thickness"]

            except UserWarning:
                raise ValueError("You must either:\n"
                                 "\t* Specify both `lower_weights` and `upper_weights`, at minimum"
                                 "\t* Give an airfoil `name` corresponding to an airfoil in the UIUC database, or a NACA airfoil.")

        ### Handle the Kulfan parameters
        self.lower_weights = lower_weights
        self.upper_weights = upper_weights
        self.leading_edge_weight = leading_edge_weight
        self.TE_thickness = TE_thickness
        self.N1 = N1
        self.N2 = N2

    def __repr__(self) -> str:
        return f"Airfoil {self.name} (Kulfan / CST parameterization)"

    def __eq__(self, other: "KulfanAirfoil") -> bool:
        if other is self:  # If they're the same object in memory, they're equal
            return True

        if not type(self) == type(other):  # If the types are different, they're not equal
            return False

        # At this point, we know that the types are the same, so we can compare the attributes
        return all([
            self.name == other.name,
            np.allclose(self.lower_weights, other.lower_weights),
            np.allclose(self.upper_weights, other.upper_weights),
            np.allclose(self.leading_edge_weight, other.leading_edge_weight),
            np.allclose(self.TE_thickness, other.TE_thickness),
            np.allclose(self.N1, other.N1),
            np.allclose(self.N2, other.N2),
        ])

    @property
    def coordinates(self) -> np.ndarray:
        return get_kulfan_coordinates(
            lower_weights=self.lower_weights,
            upper_weights=self.upper_weights,
            leading_edge_weight=self.leading_edge_weight,
            TE_thickness=self.TE_thickness,
            N1=self.N1,
            N2=self.N2,
        )

    @coordinates.setter
    def coordinates(self, value):
        raise TypeError("The coordinates of a `KulfanAirfoil` can't be modified directly, "
                        "as they're a function of the Kulfan parameters.\n"
                        "Instead, you can either modify the Kulfan parameters directly, or use the "
                        "more general (coordinate-parameterized) `asb.Airfoil` class.")

    def to_airfoil(self) -> Airfoil:
        return Airfoil(
            name=self.name,
            coordinates=self.coordinates
        )

    def draw(self,
             *args,
             draw_markers=False,
             **kwargs
             ):
        return self.to_airfoil().draw(
            *args,
            draw_markers=draw_markers,
            **kwargs
        )

    def get_aero_from_neuralfoil(self,
                                 alpha: Union[float, np.ndarray],
                                 Re: Union[float, np.ndarray],
                                 mach: Union[float, np.ndarray] = 0.,
                                 model_size: str = "large",
                                 control_surfaces: List["ControlSurface"] = None,
                                 include_360_deg_effects: bool = True,
                                 ) -> Dict[str, Union[float, np.ndarray]]:
        ### Validate inputs
        if (
                (np.length(self.lower_weights) != 8) or
                (np.length(self.upper_weights) != 8)
        ):
            raise ValueError("NeuralFoil is only trained to handle exactly 8 CST coefficients per side.")

        if (
                self.N1 != 0.5 or
                self.N2 != 1.0
        ):
            raise ValueError("NeuralFoil is only trained to handle airfoils with N1 = 0.5 and N2 = 1.0.")

        ### Set up inputs
        if control_surfaces is None:
            control_surfaces = []

        alpha = np.mod(alpha + 180, 360) - 180  # Enforce periodicity of alpha

        ##### Evaluate the control surfaces of the airfoil
        effective_d_alpha = 0.
        effective_CD_multiplier_from_control_surfaces = 1.

        for surf in control_surfaces:

            effectiveness = 1 - np.maximum(0, surf.hinge_point + 1e-16) ** 2.751428551177291
            # From XFoil-based study at `/AeroSandbox/studies/ControlSurfaceEffectiveness/`

            effective_d_alpha += surf.deflection * effectiveness

            effective_CD_multiplier_from_control_surfaces *= (
                    2 + (surf.deflection / 11.5) ** 2 - (1 + (surf.deflection / 11.5) ** 2) ** 0.5
            )
            # From fit to wind tunnel data from Hoerner, "Fluid Dynamic Drag", 1965. Page 13-13, Figure 32,
            # "Variation of section drag coefficient of a horizontal tail surface at constant C_L"

        ##### Use NeuralFoil to evaluate the incompressible aerodynamics of the airfoil
        import neuralfoil as nf
        nf_aero = nf.get_aero_from_kulfan_parameters(
            kulfan_parameters=dict(
                lower_weights=self.lower_weights,
                upper_weights=self.upper_weights,
                leading_edge_weight=self.leading_edge_weight,
                TE_thickness=self.TE_thickness,
            ),
            alpha=alpha + effective_d_alpha,
            Re=Re,
            model_size=model_size
        )

        CL = nf_aero["CL"]
        CD = nf_aero["CD"] * effective_CD_multiplier_from_control_surfaces
        CM = nf_aero["CM"]
        Cpmin_0 = nf_aero["Cpmin"]
        Top_Xtr = nf_aero["Top_Xtr"]
        Bot_Xtr = nf_aero["Bot_Xtr"]

        ##### Extend aerodynamic data to 360 degrees (post-stall) using wind tunnel behavior here.
        if include_360_deg_effects:
            from aerosandbox.aerodynamics.aero_2D.airfoil_polar_functions import airfoil_coefficients_post_stall

            CL_if_separated, CD_if_separated, CM_if_separated = airfoil_coefficients_post_stall(
                airfoil=self,
                alpha=alpha
            )
            import aerosandbox.library.aerodynamics as lib_aero

            # These values are set relatively high because NeuralFoil extrapolates quite well past stall
            alpha_stall_positive = 20
            alpha_stall_negative = -20

            # This will be an input to a tanh() sigmoid blend via asb.numpy.blend(), so a value of 1 means the flow is
            # ~90% separated, and a value of -1 means the flow is ~90% attached.
            is_separated = np.softmax(
                alpha - alpha_stall_positive,
                alpha_stall_negative - alpha
            ) / 3

            CL = np.blend(
                is_separated,
                CL_if_separated,
                CL
            )
            CD = np.exp(np.blend(
                is_separated,
                np.log(CD_if_separated + lib_aero.Cf_flat_plate(Re_L=Re, method="turbulent")),
                np.log(CD)
            ))
            CM = np.blend(
                is_separated,
                CM_if_separated,
                CM
            )
            """

            Separated Cpmin_0 model is a very rough fit to Figure 3 of:

            Shademan & Naghib-Lahouti, "Effects of aspect ratio and inclination angle on aerodynamic loads of a flat 
            plate", Advances in Aerodynamics. 
            https://www.researchgate.net/publication/342316140_Effects_of_aspect_ratio_and_inclination_angle_on_aerodynamic_loads_of_a_flat_plate

            """
            Cpmin_0 = np.blend(
                is_separated,
                -1 - 0.5 * np.sind(alpha) ** 2,
                Cpmin_0
            )

            Top_Xtr = np.blend(
                is_separated,
                0.5 - 0.5 * np.tanh(10 * np.sind(alpha)),
                Top_Xtr
            )
            Bot_Xtr = np.blend(
                is_separated,
                0.5 + 0.5 * np.tanh(10 * np.sind(alpha)),
                Bot_Xtr
            )

        ###### Add compressibility effects

        ### Step 1: compute mach_crit, the critical Mach number
        """
        Below is a function that computes the critical Mach number from the incompressible Cp_min.

        It's based on a Laitone-rule compressibility correction (similar to Prandtl-Glauert or Karman-Tsien, 
        but higher order), together with the Cp_sonic relation. When the Laitone-rule Cp equals Cp_sonic, we have reached
        the critical Mach number.

        This approach does not admit explicit solution for the Cp0 -> M_crit relation, so we instead regress a 
        relationship out using symbolic regression. In effect, this is a curve fit to synthetic data.

        See fits at: /AeroSandbox/studies/MachFitting/CriticalMach/
        """
        Cpmin_0 = np.softmin(
            Cpmin_0,
            0,
            softness=0.001
        )

        mach_crit = (
                            1.011571026701678
                            - Cpmin_0
                            + 0.6582431351007195 * (-Cpmin_0) ** 0.6724789439840343
                    ) ** -0.5504677038358711

        mach_dd = mach_crit + (0.1 / 80) ** (1 / 3)  # drag divergence Mach number
        # Relation taken from W.H. Mason's Korn Equation

        ### Step 2: adjust CL, CD, CM, Cpmin by compressibility effects
        gamma = 1.4  # Ratio of specific heats, 1.4 for air (mostly diatomic nitrogen and oxygen)
        beta_squared_ideal = 1 - mach ** 2
        beta = np.softmax(
            beta_squared_ideal,
            -beta_squared_ideal,
            softness=0.5  # Empirically tuned to data
        ) ** 0.5

        CL = CL / beta
        # CD = CD / beta
        CM = CM / beta

        # Prandtl-Glauert
        Cpmin = Cpmin_0 / beta

        # Karman-Tsien
        # Cpmin = Cpmin_0 / (
        #     beta
        #     + mach ** 2 / (1 + beta) * (Cpmin_0 / 2)
        # )

        # Laitone's rule
        # Cpmin = Cpmin_0 / (
        #         beta
        #         + (mach ** 2) * (1 + (gamma - 1) / 2 * mach ** 2) / (1 + beta) * (Cpmin_0 / 2)
        # )

        ### Step 3: modify CL based on buffet and supersonic considerations
        # Accounts approximately for the lift drop due to buffet.
        buffet_factor = np.blend(
            50 * (mach - (mach_dd + 0.04)),  # Tuned to RANS CFD data empirically
            np.blend(
                (mach - 1) / 0.1,
                1,
                0.5
            ),
            1,
        )

        # Accounts for the fact that theoretical CL_alpha goes from 2 * pi (subsonic) to 4 (supersonic),
        # following linearized supersonic flow on a thin airfoil.
        cla_supersonic_ratio_factor = np.blend(
            (mach - 1) / 0.1,
            4 / (2 * np.pi),
            1,
        )
        CL = CL * buffet_factor * cla_supersonic_ratio_factor

        # Step 4: Account for wave drag
        t_over_c = self.max_thickness()

        CD_wave = np.where(
            mach < mach_crit,
            0,
            np.where(
                mach < mach_dd,
                20 * (mach - mach_crit) ** 4,
                np.where(
                    mach < 0.97,
                    cubic_hermite_patch(
                        mach,
                        x_a=mach_dd,
                        x_b=0.97,
                        f_a=20 * (0.1 / 80) ** (4 / 3),
                        f_b=0.8 * t_over_c,
                        dfdx_a=0.1,
                        dfdx_b=0.8 * t_over_c * 8
                    ),
                    np.where(
                        mach < 1.1,
                        cubic_hermite_patch(
                            mach,
                            x_a=0.97,
                            x_b=1.1,
                            f_a=0.8 * t_over_c,
                            f_b=0.8 * t_over_c,
                            dfdx_a=0.8 * t_over_c * 8,
                            dfdx_b=-0.8 * t_over_c * 8,
                        ),
                        np.blend(
                            8 * 2 * (mach - 1.1) / (1.2 - 0.8),
                            0.8 * 0.8 * t_over_c,
                            1.2 * 0.8 * t_over_c,
                        )
                    )
                )
            )
        )

        CD = CD + CD_wave

        # Step 5: If beyond M_crit or if separated, move the airfoil aerodynamic center back to x/c = 0.5 (Mach tuck)
        has_aerodynamic_center_shift = (mach - (mach_dd + 0.06)) / 0.06

        if include_360_deg_effects:
            has_aerodynamic_center_shift = np.softmax(
                is_separated,
                has_aerodynamic_center_shift,
                softness=0.1
            )

        CM = CM + np.blend(
            has_aerodynamic_center_shift,
            -0.25 * np.cosd(alpha) * CL - 0.25 * np.sind(alpha) * CD,
            0,
        )

        return {
            "CL"       : CL,
            "CD"       : CD,
            "CM"       : CM,
            "Cpmin"    : Cpmin,
            "Top_Xtr"  : Top_Xtr,
            "Bot_Xtr"  : Bot_Xtr,
            "mach_crit": mach_crit,
            "mach_dd"  : mach_dd,
            "Cpmin_0"  : Cpmin_0,
        }

    def local_camber(self,
                     x_over_c: Union[float, np.ndarray] = np.linspace(0, 1, 101),
                     ) -> Union[float, np.ndarray]:
        # Class function
        C = (x_over_c) ** self.N1 * (1 - x_over_c) ** self.N2

        from scipy.special import comb

        def shape_function(w):
            # Shape function (Bernstein polynomials)
            N = np.length(w) - 1  # Order of Bernstein polynomials

            K = comb(N, np.arange(N + 1))  # Bernstein polynomial coefficients

            dims = (np.length(w), np.length(x_over_c))

            def wide(vector):
                return np.tile(np.reshape(vector, (1, dims[1])), (dims[0], 1))

            def tall(vector):
                return np.tile(np.reshape(vector, (dims[0], 1)), (1, dims[1]))

            S_matrix = (
                    tall(K) * wide(x_over_c) ** tall(np.arange(N + 1)) *
                    wide(1 - x_over_c) ** tall(N - np.arange(N + 1))
            )  # Bernstein polynomial coefficients * weight matrix
            S_x = np.sum(tall(w) * S_matrix, axis=0)

            # Calculate y output
            y = C * S_x
            return y

        y_lower = shape_function(self.lower_weights)
        y_upper = shape_function(self.upper_weights)

        # Add trailing-edge (TE) thickness
        y_lower -= x_over_c * self.TE_thickness / 2
        y_upper += x_over_c * self.TE_thickness / 2

        # Add Kulfan's leading-edge-modification (LEM)
        y_lower += self.leading_edge_weight * (x_over_c) * (1 - x_over_c) ** (np.length(self.lower_weights) + 0.5)
        y_upper += self.leading_edge_weight * (x_over_c) * (1 - x_over_c) ** (np.length(self.upper_weights) + 0.5)

        return (y_upper + y_lower) / 2

    def local_thickness(self,
                     x_over_c: Union[float, np.ndarray] = np.linspace(0, 1, 101),
                     ) -> Union[float, np.ndarray]:
        # Class function
        C = (x_over_c) ** self.N1 * (1 - x_over_c) ** self.N2

        from scipy.special import comb

        def shape_function(w):
            # Shape function (Bernstein polynomials)
            N = np.length(w) - 1  # Order of Bernstein polynomials

            K = comb(N, np.arange(N + 1))  # Bernstein polynomial coefficients

            dims = (np.length(w), np.length(x_over_c))

            def wide(vector):
                return np.tile(np.reshape(vector, (1, dims[1])), (dims[0], 1))

            def tall(vector):
                return np.tile(np.reshape(vector, (dims[0], 1)), (1, dims[1]))

            S_matrix = (
                    tall(K) * wide(x_over_c) ** tall(np.arange(N + 1)) *
                    wide(1 - x_over_c) ** tall(N - np.arange(N + 1))
            )  # Bernstein polynomial coefficients * weight matrix
            S_x = np.sum(tall(w) * S_matrix, axis=0)

            # Calculate y output
            y = C * S_x
            return y

        y_lower = shape_function(self.lower_weights)
        y_upper = shape_function(self.upper_weights)

        # Add trailing-edge (TE) thickness
        y_lower -= x_over_c * self.TE_thickness / 2
        y_upper += x_over_c * self.TE_thickness / 2

        # Add Kulfan's leading-edge-modification (LEM)
        y_lower += self.leading_edge_weight * (x_over_c) * (1 - x_over_c) ** (np.length(self.lower_weights) + 0.5)
        y_upper += self.leading_edge_weight * (x_over_c) * (1 - x_over_c) ** (np.length(self.upper_weights) + 0.5)

        return (y_upper - y_lower)


    def blend_with_another_airfoil(self,
                                   airfoil: Union["KulfanAirfoil", Airfoil],
                                   blend_fraction: float = 0.5,
                                   ) -> "KulfanAirfoil":
        if not isinstance(airfoil, KulfanAirfoil):
            try:
                airfoil = airfoil.to_kulfan_airfoil()
            except AttributeError:
                raise TypeError("The `airfoil` argument should be either a `KulfanAirfoil` or an `Airfoil`.\n"
                                f"You gave an object of type \"{type(airfoil)}\".")

        foil_a = self
        foil_b = airfoil
        a_fraction = 1 - blend_fraction
        b_fraction = blend_fraction

        ### Determine parameters for the blended airfoil
        name = f"{a_fraction * 100:.0f}% {self.name}, {b_fraction * 100:.0f}% {airfoil.name}"

        if not all([
            foil_a.N1 == foil_b.N1,
            foil_a.N2 == foil_b.N2,
        ]):
            raise ValueError("In order to blend two airfoils, they must have the same N1 and N2 parameters.")

        return KulfanAirfoil(
            name=name,
            lower_weights=a_fraction * foil_a.lower_weights + b_fraction * foil_b.lower_weights,
            upper_weights=a_fraction * foil_a.upper_weights + b_fraction * foil_b.upper_weights,
            leading_edge_weight=a_fraction * foil_a.leading_edge_weight + b_fraction * foil_b.leading_edge_weight,
            TE_thickness=a_fraction * foil_a.TE_thickness + b_fraction * foil_b.TE_thickness,
            N1=foil_a.N1,
            N2=foil_a.N2,
        )
