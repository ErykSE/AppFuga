from apps.backend.algorithms.energy_manager_class import EnergyManager
from apps.backend.devices.bess_class import BESS
from apps.backend.terms.osd_class import OSD
from apps.backend.devices.pv_class import PV


def main():
    pv = PV(power=1.2, efficiency=15, sunlight=80)  # Example values
    bess = BESS(power=50, capacity=200, charged=False)  # Example values
    osd = OSD(power=75, tariff=0.15)  # Example values
    manager = EnergyManager(pv, bess, osd)

    scenario = "export"  # Example scenario
    if scenario == "export":
        manager.manage_export()
        print(type(pv))
    elif scenario == "import":
        manager.manage_import()
        print("fail")


if __name__ == "__main__":
    main()
