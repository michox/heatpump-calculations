from HeatPumpStudy import HeatPumpStudy
from tespy.components import (Valve, Sink, Source, Pump, Compressor, Condenser, Turbine, CycleCloser, HeatExchangerSimple)
from tespy.connections import Connection
from CoolProp.CoolProp import PropsSI as PSI

class RegularHeatPumpStudy(HeatPumpStudy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


    def setup_components_and_connections(self):
        expansion_type = Valve
        if self.expansion_device == "expander":
            expansion_type = Turbine
        elif self.expansion_device != "expansionValve":
            raise ValueError("expansion_device must be either 'expansionValve' or 'expander'")
    
        component_list = [
            ("evaporator", HeatExchangerSimple),
            ("compressor", Compressor),
            ("condenser", HeatExchangerSimple),
            (self.expansion_device, expansion_type),
            ("cycle_closer", CycleCloser),
        ]

        connection_list = [
            ("cycle_closer", "out1", "evaporator", "in1"),
            ("evaporator", "out1", "compressor", "in1"),
            ("compressor", "out1", "condenser", "in1"),
            ("condenser", "out1", self.expansion_device, "in1"),
            (self.expansion_device, "out1", "cycle_closer", "in1")
        ]
        self.add_components_and_connections(component_list, connection_list)
        #self.add_condenser_cooling()# need to change condenser to Condenser when used and HeatExchangerSimple when not used


    def set_boundary_conditions(self, T_cond=80, T_evap=20):

        p_cond = PSI("P", "Q", 0, "T", 273.15 + T_cond, self.working_fluid) / 1e5
        p_evap = PSI("P", "Q", 1, "T", 273.15 + T_evap, self.working_fluid) / 1e5
        

        self.comp["evaporator"].set_attr(pr=0.98)
        self.conn["evaporator-compressor"].set_attr(p=p_evap, x=1, fluid={self.working_fluid: 1})
        self.comp["compressor"].set_attr(eta_s=self.compressor_efficiency)
        self.comp["condenser"].set_attr(pr=0.98, Q=-self.Q_out)
        if self.expansion_device == "expansionValve":
            self.conn["condenser-expansionValve"].set_attr(x=0, p=p_cond)
        elif self.expansion_device == "expander":
            self.conn["condenser-expander"].set_attr(x=0.01, p=p_cond)            
            self.comp["expander"].set_attr(eta_s=self.expander_efficiency)

        return self