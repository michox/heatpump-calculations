from HeatPumpStudy import HeatPumpStudy, alternate
from tespy.components import (Valve, Sink, Source, Pump, Compressor,
                              HeatExchanger, Turbine, CycleCloser, HeatExchangerSimple)
from tespy.connections import Connection
from CoolProp.CoolProp import PropsSI as PSI


class IntercoolerHeatPumpStudy(HeatPumpStudy):
    def __init__(self, exchange_direction="counterflow", **kwargs):
        self.exchange_direction = exchange_direction
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
            self.repeat_comp("intermediate_hx", HeatExchanger)),
                            (f"compressor_{N+1}", Compressor),
                            ("condenser", HeatExchangerSimple),
                            (self.expansion_device, expansion_type),
                            ("cycle_closer", CycleCloser),
        ]

        # ------------------- Connections -------------------
        connection_list = [
                            ("cycle_closer", "out1", "evaporator", "in1"),
                            ("evaporator", "out1", "intermediate_hx_1", "in2"),
           *self.repeat_conn("intermediate_hx", "out2", "intermediate_hx", "in2", out_id_increment=1, in_id_increment=2, N=N-1),
                            (f"intermediate_hx_{N}", "out2", "compressor_1", "in1"),
        ]
        
        if self.exchange_direction == "parallel_flow":
            connection_list.extend(
 *alternate(self.repeat_conn("compressor", "out1", "intermediate_hx", "in1"),
            self.repeat_conn("intermediate_hx", "out1", "compressor", "in1", out_id_increment=1, in_id_increment=2))
            )
        elif self.exchange_direction == "counterflow":
            for i in range(N):
                connection_list.extend([
                            (f"compressor_{i+1}", "out1", f"intermediate_hx_{N-i}", "in1"),
                            (f"intermediate_hx_{N-i}", "out1", f"compressor_{i+2}", "in1")
                ])
        
        connection_list.extend([
                            (f"compressor_{N+1}", "out1", "condenser", "in1"),
                            ("condenser", "out1", "expansionValve", "in1"),
                            ("expansionValve", "out1", "cycle_closer", "in1"),
        ])
        # fmt: on
    
        self.add_components_and_connections(component_list, connection_list)
        # self.add_condenser_cooling()# need to change condenser type to Condenser when used and HeatExchangerSimple when not used

    def set_boundary_conditions(self, T_cond=80, T_evap=-10):

        p_cond = PSI("P", "Q", 0, "T", 273.15 +
                     T_cond, self.working_fluid) / 1e5
        p_evap = PSI("P", "Q", 1, "T", 273.15 +
                     T_evap, self.working_fluid) / 1e5

        self.comp["evaporator"].set_attr(pr=0.98)
        self.conn["evaporator-intermediate_hx_1"].set_attr(
            p=p_evap, x=1, fluid={self.working_fluid: 1})

        for i in range(self.N):
            self.comp[f"compressor_{i+1}"].set_attr(
                eta_s=self.compressor_efficiency)
            self.comp[f"intermediate_hx_{i+1}"].set_attr(
                pr1=0.995, pr2=0.995, Q=-self.Q_out*(T_cond-T_evap)/1000*2) # Q_out/5 is a guess for the heat transfer rate in the intermediate heat exchangers
        for conn in self.conn:
            if conn.startswith("compressor_"):
                i = int(conn.split("_")[1].split("-")[0])
                self.conn[conn].set_attr(p=p_evap+(p_cond-p_evap)*(i)/(self.N+1)) #split the pressure difference equally between the compressors
            elif conn.startswith("intermediate_hx_") and "compressor" in conn:
                if "compressor_1" not in conn:
                    #self.conn[conn].set_attr(x=1) 
                    pass

        self.comp[f"compressor_{self.N+1}"].set_attr(eta_s=self.compressor_efficiency)
        self.comp["condenser"].set_attr(pr=0.98, Q=-self.Q_out)
        if self.expansion_device == "expansionValve":
            self.conn["condenser-expansionValve"].set_attr(x=0)
        elif self.expansion_device == "expander":
            self.conn["condenser-expander"].set_attr(x=0.01)            
            self.comp["expander"].set_attr(eta_s=self.expander_efficiency)

        return self

            
