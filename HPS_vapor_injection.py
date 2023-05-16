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
                                    ("evaporator", HeatExchangerSimple),
         *alternate(self.repeat_comp("compressor", Compressor),
                    self.repeat_comp("merge", Merge)),        
                                    (f"compressor_{N+1}", Compressor),
                                    ("condenser", HeatExchangerSimple),
         *alternate(self.repeat_comp(self.expansion_device, expansion_type),
                    self.repeat_comp("splitter", Splitter)),
                                    (f"{self.expansion_device}_{N+1}", expansion_type),
                                    ("cycle_closer", CycleCloser),
        ]

        # ------------------- Connections -------------------
        connection_list = [         
                                    ("cycle_closer", "out1", "evaporator", "in1", "1"),                                                     
                                    ("evaporator", "out1", "compressor_1", "in1", "2"),
         *alternate(self.repeat_conn("compressor", "out1", "merge", "in1", "3_1"),
                    self.repeat_conn("merge", "out1", "compressor", "in1", "3_2", out_id_increment=1, in_id_increment=2)),
                                    (f"compressor_{N+1}", "out1", "condenser", "in1", "4"),
                                    ("condenser", "out1", f"{self.expansion_device}_1", "in1", "5_3"),
         *alternate(self.repeat_conn(self.expansion_device, "out1", "splitter", "in1", "6_1"),
                    self.repeat_conn("splitter", "out1", self.expansion_device, "in1", "6_2", out_id_increment=1, in_id_increment=2)),
                                    (f"{self.expansion_device}_{N+1}", "out1", "cycle_closer", "in1", "0"),
        ]
        connection_list.extend(
            (f"splitter_{self.N - i}","out2",f"merge_{i + 1}","in2",f"3_{i + 1}") for i in range(N)
        )
        # fmt: on

        self.add_components_and_connections(component_list, connection_list)
        # self.add_condenser_cooling()# need to change condenser type to Condenser when used and HeatExchangerSimple when not used

    
    def set_boundary_conditions(self, T_cond=80, T_evap=-10):

        p_cond = PSI("P", "Q", 0, "T", 273.15 + T_cond, self.working_fluid) / 1e5
        p_evap = PSI("P", "Q", 1, "T", 273.15 + T_evap, self.working_fluid) / 1e5
        m0=3.650e-02 #experimental starting value for mass flow
        #self.print_components()
        #self.print_connections()

        self.comp["evaporator"].set_attr(pr=0.98)           # certain
        self.conn["evaporator-compressor_1"].set_attr(      # certain
           x=1, p=p_evap, m0=m0, fluid={self.working_fluid: 1, "water": 0}
        )
        # ---------------- efficiencies -------------------

        for i in range(self.N+1):
            self.comp[f"compressor_{i+1}"].set_attr(eta_s=self.compressor_efficiency) # certain
            if self.expansion_device == "expander":
                self.comp[f"expander_{i+1}"].set_attr(eta_s=self.expander_efficiency) # certain

        self.conn[f"compressor_{self.N+1}-condenser"].set_attr(m=m0,T=T_cond+5) # the goal is to be as close as possible to T_cond at the outlet to reduce temperature difference in the compressor
        
        self.comp["condenser"].set_attr(pr=0.98)#, Q=-self.Q_out
        
        if self.expansion_device == "expansionValve":
            self.conn["condenser-expansionValve_1"].set_attr(x=0)
        elif self.expansion_device == "expander":
            self.conn["condenser-expander_1"].set_attr(x=0.05)

        # because our desired conditions have unstable starting values, 
        # we first set the massflow of the injection manually, solve, 
        # then set the compressor intake conditions (x=1)

        for conn in self.conn:
            if conn.startswith("splitter") and "merge" in conn:
                i = int(conn.split("merge_")[1])
                p = p_evap + (p_cond - p_evap) * (i) / (self.N + 1)
                self.conn[conn].set_attr(p=p)
                self.conn[conn].set_attr(m=m0/10/(self.N))
        
        self.solve()
        self.network.print_results()

        
        for conn in self.conn:
            if conn.startswith("merge") and "compressor" in conn:
                self.conn[conn].set_attr(x=1)
            elif conn.startswith("splitter") and "merge" in conn:
                self.conn[conn].set_attr(m=None)
        #self.conn[f"compressor_{self.N+1}-condenser"].set_attr(m=None)
        #self.comp["condenser"].set_attr(Q=-self.Q_out)


        return self


    def get_results(self):
        results = {}
        for comp in self.comp.values():
            
            if isinstance(comp, (HeatExchanger, Merge)) and "condenser" not in comp.label :
                results[f"{comp.label}_1"] = comp.get_plotting_data()[1]
                #results[f"{comp.label}_2"] = comp.get_plotting_data()[2]
            elif not isinstance(comp, (CycleCloser, Splitter)):
                results[comp.label] = comp.get_plotting_data()[1]
        return results