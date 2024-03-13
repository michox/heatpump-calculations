from HeatPumpStudy import HeatPumpStudy
from CoolProp.CoolProp import PropsSI as PSI
from tespy.components import (
    Turbine,
    Compressor,
    Source,
    Sink,
    HeatExchangerSimple,
    CycleCloser,
)

""" 
Direct air cooler with energy recovery: 
Air is taken from the source at 100% humidity and 40°C and compressed by compressor to 120°C
air is then passed through a simple heat exchanger and cooled down 
then the air is reduced again to 1 bar so that the final temperature going into the Sink is 15°C .
Maximum cooling power: 150W
"""

class MobileAirConditioner(HeatPumpStudy):
    def __init__(self, Q_in, **kwargs):
        self.Q_in = Q_in
        super().__init__(**kwargs)

    def setup_components_and_connections(self):
        N = self.N

        # ------------------- Components -------------------

        component_list = [
            ("source", Source),
            ("compressor", Compressor),
            ("heat_exchanger", HeatExchangerSimple),
            ("expander", Turbine),
            ("sink", Sink),
        ]

        # ------------------- Connections -------------------
        connection_list = [
            ("source", "out1", "compressor", "in1"),
            ("compressor", "out1", "heat_exchanger", "in1"),
            ("heat_exchanger", "out1", "expander", "in1"),
            ("expander", "out1", "sink", "in1"),
        ]


        self.add_components_and_connections(component_list, connection_list)

    def set_boundary_conditions(self, T_cond=80, T_evap=-10):
        p_cond = PSI("P", "Q", 0, "T", 273.15 + T_cond, self.working_fluid) / 1e5
        p_evap = PSI("P", "Q", 1, "T", 273.15 + T_evap, self.working_fluid) / 1e5

        if self.expansion_device == "expansionValve":
            self.conn["cycle_closer-expansionValve_1"].set_attr(x=0, p=p_cond)
        elif self.expansion_device == "expander":
            self.conn["cycle_closer-expander_1"].set_attr(x=0.05, p=p_cond)

        # because our desired conditions have unstable starting values,
        # we first set the massflow of the injection manually, solve,
        # then set the conditions we actually want and solve again

        for conn in self.conn:
            if conn.startswith("splitter") and "merge" in conn:
                i = int(conn.split("merge_")[1])
                self.conn[conn].set_attr(p=p[i])
                self.conn[conn].set_attr(m=0.2)

        self.comp["evaporator"].set_attr(pr=0.98)
        self.conn["evaporator-compressor_1"].set_attr(
            x=1, p=p_evap, fluid={self.working_fluid: 1}
        )
        # ---------------- efficiencies -------------------

        for i in range(self.N + 1):
            self.comp[f"compressor_{i+1}"].set_attr(eta_s=self.compressor_efficiency)
            if self.expansion_device == "expander":
                self.comp[f"expander_{i+1}"].set_attr(eta_s=self.expander_efficiency)

        self.conn[f"compressor_{self.N+1}-condenser"].set_attr(m=m0)
        self.comp["condenser"].set_attr(pr=0.98)

        # in case we have previously set the boundary conditions to a different value, we need to unset the yet unset values before we solve
        for conn in self.conn:
            if conn.startswith("merge") and "compressor" in conn:
                self.network.get_conn(conn).set_attr(x=None)
        self.network.get_comp("condenser").set_attr(Q=None)

        self.network.solve("design")
        # now set the actual conditions we want

        for conn in self.conn:
            if conn.startswith("merge") and "compressor" in conn:
                self.network.get_conn(conn).set_attr(x=1)
            if conn.startswith("splitter") and "merge" in conn:
                self.network.get_conn(conn).set_attr(m=None)

        self.network.get_conn(f"compressor_{self.N+1}-condenser").set_attr(m=None)
        self.network.get_comp("condenser").set_attr(Q=-self.Q_out)

        return self

    def get_results(self):
        results = {}
        for comp in self.comp.values():
            if not isinstance(comp, (CycleCloser, Sink, Source)):
                results[comp.label] = comp.get_plotting_data()[1]
        return results
