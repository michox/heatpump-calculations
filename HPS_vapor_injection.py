import numpy as np
from HeatPumpStudy import HeatPumpStudy, alternate
from tespy.components import (
    Valve,
    Compressor,
    Splitter,
    Merge,
    HeatExchanger,
    Turbine,
    CycleCloser,
    HeatExchangerSimple,
)
from tespy.connections import Connection


from CoolProp.CoolProp import PropsSI as PSI

class VaporInjectionHeatPumpStudy(HeatPumpStudy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def setup_components_and_connections(self):
        N = self.N
        expansion_type = Valve
        if self.expansion_device == "expander":
            expansion_type = Turbine
        elif self.expansion_device != "expansionValve":
            raise ValueError("expansion_device must be either 'expansionValve' or 'expander'")

        # ------------------- Components -------------------
        # fmt: off

        component_list = [
         *alternate(self.repeat_comp(self.expansion_device, expansion_type),
                    self.repeat_comp("splitter", Splitter)),
                                    (f"{self.expansion_device}_{N+1}", expansion_type),
                                    ("evaporator", HeatExchangerSimple),
         *alternate(self.repeat_comp("compressor", Compressor),
                    self.repeat_comp("merge", Merge)),        
                                    (f"compressor_{N+1}", Compressor),
                                    ("condenser", HeatExchangerSimple),
                                    ("cycle_closer", CycleCloser),
        ]

        # ------------------- Connections -------------------
        connection_list = [         
                                    ("cycle_closer", "out1",f"{self.expansion_device}_1", "in1"),
         *alternate(self.repeat_conn(self.expansion_device, "out1", "splitter", "in1"),
                    self.repeat_conn("splitter", "out1", self.expansion_device, "in1", out_id_increment=1, in_id_increment=2)),
                                    (f"{self.expansion_device}_{N+1}", "out1", "evaporator", "in1"),
                                    ("evaporator", "out1", "compressor_1", "in1"),
         *alternate(self.repeat_conn("compressor", "out1", "merge", "in1"),
                    self.repeat_conn("merge", "out1", "compressor", "in1", out_id_increment=1, in_id_increment=2)),
                                    (f"compressor_{N+1}", "out1", "condenser", "in1"),
                                    (f"condenser", "out1", "cycle_closer", "in1"),
        ]
        connection_list.extend(
            (f"splitter_{self.N - i}","out2",f"merge_{i + 1}","in2") for i in range(N)
        )
        # fmt: on
  

        self.add_components_and_connections(component_list, connection_list)
        # self.add_condenser_cooling()# need to change condenser type to Condenser when used and HeatExchangerSimple when not used

    
    def set_boundary_conditions(self, T_cond=80, T_evap=-10):

        p_cond = PSI("P", "Q", 0, "T", 273.15 + T_cond, self.working_fluid) / 1e5
        p_evap = PSI("P", "Q", 1, "T", 273.15 + T_evap, self.working_fluid) / 1e5
        p = np.geomspace(p_evap, p_cond, self.N + 2)
        m0=2 # starting value for mass flow

        if self.expansion_device == "expansionValve":
            self.conn["cycle_closer-expansionValve_1"].set_attr(x=0,p=p_cond)
        elif self.expansion_device == "expander":
            self.conn["cycle_closer-expander_1"].set_attr(x=0.05,p=p_cond)

        # because our desired conditions have unstable starting values, 
        # we first set the massflow of the injection manually, solve, 
        # then set the conditions we actually want and solve again

        for conn in self.conn:
            if conn.startswith("splitter") and "merge" in conn:
                i = int(conn.split("merge_")[1])
                self.conn[conn].set_attr(p=p[i])
                self.conn[conn].set_attr(m=.2)

        self.comp["evaporator"].set_attr(pr=0.98)
        self.conn["evaporator-compressor_1"].set_attr(      
           x=1, p=p_evap, fluid={self.working_fluid: 1}
        )
        # ---------------- efficiencies -------------------

        for i in range(self.N+1):
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
            if isinstance(comp, (HeatExchanger )) and "condenser" not in comp.label :
                results[f"{comp.label}_1"] = comp.get_plotting_data()[1]
                #results[f"{comp.label}_2"] = comp.get_plotting_data()[2] 
            elif not isinstance(comp, (CycleCloser, Splitter)):
                results[comp.label] = comp.get_plotting_data()[1]
        return results