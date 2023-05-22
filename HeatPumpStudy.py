import numpy as np
import matplotlib.pyplot as plt
from tespy.components import (
    Valve,
    Sink,
    Source,
    Pump,
    Compressor,
    Merge,
    Splitter,
    Condenser,
    Turbine,
    CycleCloser,
    HeatExchangerSimple,
    HeatExchanger,
)
from tespy.components.component import Component
from tespy.connections import Connection
from tespy.networks import Network
from CoolProp.CoolProp import PropsSI as PSI
from typing import Dict
import inspect


class HeatPumpStudy:
    def __init__(
        self,
        N=1,
        Q_out=8e3,
        working_fluid="R290",
        compressor_efficiency=0.8,
        expander_efficiency=0.8,
        expansion_device="expansionValve",
    ):
        self.N = N
        self.Q_out = Q_out
        self.working_fluid = working_fluid
        self.compressor_efficiency = compressor_efficiency
        self.expander_efficiency = expander_efficiency
        self.expansion_device = expansion_device
        self.comp: Dict[str, Component] = {}
        self.conn: Dict[str, Connection] = {}
        self.network = None
        self.setup_network()

    def setup_network(self, iterinfo=False):
        self.comp = {}
        self.conn = {}
        self.network = Network(fluids=[self.working_fluid], iterinfo=iterinfo)
        self.network.set_attr(
            p_unit="bar", T_unit="C", h_unit="kJ / kg", m_unit="kg / s"
        )

        self.setup_components_and_connections()
        self.network.add_conns(*list(self.conn.values()))
        self.set_boundary_conditions()
        return self

    def add_components_and_connections(self, component_list, connection_list):
        for name, comp_class in component_list:
            self.comp[name] = comp_class(name)

        for comp1, out, comp2, inp in connection_list:
            self.conn[f"{comp1}-{comp2}"] = Connection(
                self.comp[comp1], out, self.comp[comp2], inp, label=f"{comp1}-{comp2}"
            )

    def print_components(self):
        for name, comp in self.comp.items():
            print(name)

    def print_connections(self):
        for name, conn in self.conn.items():
            print(name)

    def solve(self, mode="design", **args):
        self.network.solve(mode=mode, design_path="HeatPumpStudy", **args)
        return self

    def set_boundary_conditions(self, T_cond=60, T_evap=10):
        print("setting boundary conditions is not implemented in parent class. use subclass")
        # throw error: function not implemented in parent class. use subclass
        pass

    """ 
        summary: repeat a component N times
        param: name: str - name of component
        param: type: Component - type of component
    """

    def repeat_comp(self, name: str, type: type[Component], N=-1):
        if N == -1:
            N = self.N
        return [(f"{name}_{i+1}", type) for i in range(N)]

    """ 
        summary: repeat a connection N times
        param: out_connection_label: str - name of component that connection is coming out of
        param: out_port_label: str - name of port that connection is coming out of
        param: in_connection_label: str - name of component that connection is going into
        param: in_port_label: str - name of port that connection is going into
        param: conn_label: str - name of connection
        param: out_id_increment: int - increment of out_connection_label from which to start repeating
        param: in_id_increment: int - increment of in_connection_label from which to start repeating
        param: N: int - number of times to repeat
    """

    def repeat_conn(
        self,
        out_connection_label: str,
        out_port_label: str,
        in_connection_label: str,
        in_port_label: str,
        out_id_increment=1,
        in_id_increment=1,
        N=-1,
    ):
        if N == -1:
            N = self.N
        return [
            (
                f"{out_connection_label}_{i+out_id_increment}",
                out_port_label,
                f"{in_connection_label}_{i+in_id_increment}",
                in_port_label,                
            )
            for i in range(N)
        ]


    def add_condenser_cooling(self):
        component_list = [
            # ("condenser", HeatExchanger), TODO: replace simple condenser with normal condenser
            ("consumer_pump", Pump),
            ("consumer", HeatExchangerSimple),
            ("consumer_cycle_closer", CycleCloser),
        ]

        connection_list = [
            ("consumer_cycle_closer", "out1", "consumer_pump", "in1", "11"),
            ("consumer_pump", "out1", "condenser", "in2", "12"),
            ("condenser", "out2", "consumer", "in1", "13"),
            ("consumer", "out1", "consumer_cycle_closer", "in1", "10"),
        ]
        self.add_components_and_connections(component_list, connection_list)
        # TODO: replace old connections to the simple condenser with new connections to the normal condenser

        self.comp["consumer_pump"].set_attr(eta_s=0.8)
        self.conn["consumer_pump-condenser"].set_attr(
            T=20, p=10, fluid={"water": 1, self.working_fluid: 0}
        )
        self.conn["condenser-consumer"].set_attr(T=40)
        self.comp["consumer"].set_attr(pr=0.99, Q=-self.Q_out)

    def calculate_cop(self, consumer="condenser"):
        Q = abs(self.comp[consumer].Q.val)
        W = sum(
            comp.P.val for comp in self.comp.values() if isinstance(comp, (Compressor, Turbine))
        )
        return Q / W

    def efficiency_matrix(self):
        # Calculate the efficiency of the heat pump system for each combination of condensation and evaporation temperature in 5K increments
        condensation_temps = np.arange(50, 71, 5)
        evaporation_temps = np.arange(-10, 11, 5)
        efficiency_matrix = np.zeros((len(condensation_temps), len(evaporation_temps)))

        for i, T_cond in enumerate(condensation_temps):
            for j, T_evap in enumerate(evaporation_temps):
                # Set the boundary conditions for the condensation and evaporation temperatures
                self.set_boundary_conditions(T_cond, T_evap)

                # Solve the network
                self.network.solve("design")

                COP = self.calculate_cop()

                # Store the COP in the efficiency matrix
                efficiency_matrix[i, j] = COP

        return efficiency_matrix

    def offdesign_efficiency_matrix(self):
        condensation_temps = np.arange(50, 71, 5)
        evaporation_temps = np.arange(-10, 11, 5)
        efficiency_matrix = np.zeros((len(condensation_temps), len(evaporation_temps)))

        for i, T_cond in enumerate(condensation_temps):
            for j, T_evap in enumerate(evaporation_temps):
                # Set the boundary conditions for the condensation and evaporation temperatures
                self.set_boundary_conditions(T_cond, T_evap)

                # Solve the network in off-design mode
                self.network.solve("offdesign")

                COP = self.calculate_cop()

                # Store the COP in the efficiency matrix
                efficiency_matrix[i, j] = COP

        return efficiency_matrix

    def get_results(self):
        results = {}
        for comp in self.comp.values():
            if isinstance(comp, (HeatExchanger, Merge)) and "condenser" not in comp.label :
                results[f"{comp.label}_1"] = comp.get_plotting_data()[1]
                results[f"{comp.label}_2"] = comp.get_plotting_data()[2]
            elif not isinstance(comp, (CycleCloser, Splitter)):
                results[comp.label] = comp.get_plotting_data()[1]
        return results

    def plot_ts_diag(self, filename, x_min=1500, x_max=2500, y_min=-30, y_max=120):
        from fluprodia import FluidPropertyDiagram

        diagram = FluidPropertyDiagram(self.working_fluid)
        diagram.set_unit_system(T="°C", p="bar", h="kJ/kg")

        result_dict = self.get_results()
        for key, data in result_dict.items():
            result_dict[key]["datapoints"] = diagram.calc_individual_isoline(**data)

        diagram.set_limits(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)
        T = np.arange(-50, 101, 5)
        Q = np.linspace(0, 1, 41)
        diagram.set_isolines(T=T, Q=Q)
        diagram.calc_isolines()
        mydata = {"Q": {"values": Q}, "T": {"values": T}}
        diagram.calc_isolines()
        diagram.draw_isolines("Ts", isoline_data=mydata)

        for key in result_dict:
            datapoints = result_dict[key]["datapoints"]
            diagram.ax.plot(datapoints["s"], datapoints["T"], color="#ff0000")
            diagram.ax.scatter(datapoints["s"][0], datapoints["T"][0], color="#ff0000")
            # diagram.ax.annotate(key, (datapoints['s'][0], datapoints['T'][0]), textcoords="offset points", xytext=(5,5), ha='left')

        diagram.save(f"{filename}.svg")

    def plot_logph_diag(self, filename, x_min=300, x_max=700, y_min=1e0, y_max=6e1):
        from fluprodia import FluidPropertyDiagram

        result_dict = self.get_results()

        diagram = FluidPropertyDiagram(self.working_fluid)
        diagram.set_unit_system(T="°C", p="bar", h="kJ/kg")

        for key, data in result_dict.items():
            result_dict[key]["datapoints"] = diagram.calc_individual_isoline(**data)

        diagram.set_limits(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)

        T = np.arange(-50, 201, 5)
        Q = np.linspace(0, 1, 41)
        diagram.set_isolines(T=T, Q=Q)
        diagram.calc_isolines()
        mydata = {"Q": {"values": Q}, "T": {"values": T}}
        diagram.calc_isolines()
        diagram.draw_isolines("logph", isoline_data=mydata)

        for key in result_dict:
            datapoints = result_dict[key]["datapoints"]
            diagram.ax.plot(datapoints["h"], datapoints["p"], color="#ff0000")
            diagram.ax.scatter(datapoints["h"][0], datapoints["p"][0], color="#ff0000")
            # diagram.ax.annotate(key, (datapoints['h'][0], datapoints['p'][0]), textcoords="offset points", xytext=(5,5), ha='left')

        diagram.save(f"{filename}.svg")

    def plot_efficiency(self, filename):
        efficiency_matrix = self.efficiency()

        condensation_temps = np.arange(50, 71, 5)
        evaporation_temps = np.arange(-10, 11, 5)

        fig, ax = plt.subplots()
        c = ax.contourf(
            evaporation_temps, condensation_temps, efficiency_matrix, levels=20
        )
        fig.colorbar(c, ax=ax)

        ax.set_title("Heat Pump Efficiency")
        ax.set_xlabel("Evaporation Temperature (°C)")
        ax.set_ylabel("Condensation Temperature (°C)")

        plt.savefig(f"{filename}.png")
        plt.show()


from itertools import chain


def alternate(*lists):
    return list(chain.from_iterable(zip(*lists)))
