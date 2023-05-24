from HeatPumpStudy import HeatPumpStudy, alternate
from tespy.components import (Valve, Sink, Source, Pump, Compressor,
                              HeatExchanger, Turbine, CycleCloser, HeatExchangerSimple)
from tespy.connections import Connection
from tespy.networks import Network
from CoolProp.CoolProp import PropsSI as PSI


class InternalCondenserHeatPumpStudy(HeatPumpStudy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def setup_network(self, iterinfo=False):
        self.comp = {}
        self.conn = {}
        self.network = Network(fluids=[self.working_fluid, "water"], iterinfo=iterinfo)
        self.network.set_attr(
            p_unit="bar", T_unit="C", h_unit="kJ / kg", m_unit="kg / s"
        )

        self.setup_components_and_connections()
        self.network.add_conns(*list(self.conn.values()))
        self.set_boundary_conditions()
        return self


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
            # heat pump
                            ("evaporator", HeatExchangerSimple),
 *alternate(self.repeat_comp("compressor", Compressor),
            self.repeat_comp("intermediate_hx", HeatExchanger)),
                            (f"compressor_{N+1}", Compressor),
                            ("condenser", HeatExchanger),
                            (self.expansion_device, expansion_type),
                            ("cycle_closer", CycleCloser),
            # consumer
                            ("consumer_pump", Pump),
                            ("consumer", HeatExchangerSimple),
                            ("consumer_cycle_closer", CycleCloser),
        ]

        # ------------------- Connections -------------------
        connection_list = [
            # heat pump
                            ("cycle_closer", "out1", "evaporator", "in1"),
                            ("evaporator", "out1", "compressor_1", "in1"),
 *alternate(self.repeat_conn("compressor", "out1", "intermediate_hx", "in1"),
            self.repeat_conn("intermediate_hx", "out1", "compressor", "in1", out_id_increment=1, in_id_increment=2)),
                            (f"compressor_{N+1}", "out1", "condenser", "in1"),
                            ("condenser", "out1", self.expansion_device, "in1"),
                            (self.expansion_device, "out1", "cycle_closer", "in1"),
            # consumer
                            ("consumer_cycle_closer", "out1", "consumer_pump", "in1"),
                            ("consumer_pump", "out1", "intermediate_hx_1", "in2"),
           *self.repeat_conn("intermediate_hx", "out2", "intermediate_hx", "in2", out_id_increment=1, in_id_increment=2, N=self.N-1),                            
                            (f"intermediate_hx_{N}", "out2","condenser", "in2"),
                            ("condenser", "out2", "consumer", "in1"),
                            ("consumer", "out1", "consumer_cycle_closer", "in1"),
    ]
        # fmt: on

        self.add_components_and_connections(component_list, connection_list)
        # self.add_condenser_cooling()# need to change condenser type to Condenser when used and HeatExchangerSimple when not used

    def set_boundary_conditions(self, T_cond=80, T_evap=-10, T_consumer=60):

        # Todo: make work with N > 1

        p_cond = PSI("P", "Q", 0, "T", 273.15 +
                     T_cond, self.working_fluid) / 1e5
        p_evap = PSI("P", "Q", 1, "T", 273.15 +
                     T_evap, self.working_fluid) / 1e5

        #self.print_components()
        #self.print_connections()

        self.comp["evaporator"].set_attr(pr=0.98)
        self.conn["evaporator-compressor_1"].set_attr(
            p=p_evap, fluid={self.working_fluid: 1, "water": 0})

        for i in range(self.N):
            self.comp[f"compressor_{i+1}"].set_attr(
                eta_s=self.compressor_efficiency)
            self.comp[f"intermediate_hx_{i+1}"].set_attr(pr1=0.995, pr2=0.995) 

            
        self.conn[f"compressor_{self.N+1}-condenser"].set_attr(p=p_cond, T=T_cond+3)
        for i in range(self.N+1, 0, -1):
            for conn in self.conn:
                if conn.endswith(f"compressor_{i}"):
                    self.conn[conn].set_attr(x=1)
            
        self.comp[f"compressor_{self.N+1}"].set_attr(eta_s=self.compressor_efficiency)
        self.comp["condenser"].set_attr(pr1=0.98, pr2=0.98)
        if self.expansion_device == "expansionValve":
            self.conn["condenser-expansionValve"].set_attr(x=0)
        elif self.expansion_device == "expander":
            self.conn["condenser-expander"].set_attr(x=0.05)            
            self.comp["expander"].set_attr(eta_s=self.expander_efficiency)

        # consumer
        self.comp["consumer_pump"].set_attr(eta_s=1)
        self.conn["consumer_pump-intermediate_hx_1"].set_attr(
            T=T_consumer-10, p=10, fluid={"water": 1, self.working_fluid: 0})
        
        self.conn["condenser-consumer"].set_attr(T=T_consumer)
        self.comp["consumer"].set_attr(pr=0.99, Q=-self.Q_out)

        return self


    def get_results(self):
        return {
            comp.label: comp.get_plotting_data()[1]
            for comp in self.comp.values()
            if not isinstance(comp, CycleCloser)
        }
    
    def calculate_cop(self):
        Q = abs(self.comp["consumer"].Q.val)
        W = sum(
            comp.P.val for comp in self.comp.values() if isinstance(comp, (Compressor, Turbine))
        )
        return Q / W