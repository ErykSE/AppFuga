import pytest
from apps.backend.devices.energy_source_class import EnergySource


@pytest.fixture
def valid_data():
    return {
        "id": 1,
        "name": "Test Source",
        "priority": 1,
        "max_output": 100,
        "min_output": 10,
        "actual_output": 50,
        "switch_status": True,
        "device_status": "online",
    }


def test_create_instance(valid_data):
    source = EnergySource.create_instance(valid_data)
    assert source is not None
    assert source.id == 1
    assert source.name == "Test Source"
    assert source.is_valid == True


def test_create_instance_invalid_data(valid_data):
    invalid_data = valid_data.copy()
    invalid_data["id"] = -1
    source = EnergySource.create_instance(invalid_data)
    assert source is None


def test_activate_deactivate(valid_data):
    source = EnergySource.create_instance(valid_data)
    source.deactivate()
    assert source.device_status == "offline"
    assert source.switch_status == False
    source.activate()
    assert source.device_status == "online"
    assert source.switch_status == True


def test_increase_output(valid_data):
    source = EnergySource.create_instance(valid_data)
    percent, amount = source.increase_output(20, is_percent=True)
    assert source.actual_output == 60
    assert percent == pytest.approx(20)
    assert amount == pytest.approx(10)


"""
def test_increase_output(valid_data):
    source = EnergySource.create_instance(valid_data)
    
    print(f"\nPoczątkowa moc wyjściowa: {source.get_actual_output()} kW")
    
    percent_increased, amount_increased = source.increase_output(20, is_percent=True)
    
    print(f"Wywołano increase_output(20, is_percent=True)")
    print(f"Moc wyjściowa po zwiększeniu: {source.get_actual_output()} kW")
    
    assert source.get_actual_output() == pytest.approx(60)
    assert percent_increased == pytest.approx(20)
    assert amount_increased == pytest.approx(10)

@pytest.mark.parametrize("increase_amount, is_percent, expected_output", [
    pytest.param(20, True, 60, id="Increase by 20%"),
    pytest.param(10, False, 60, id="Increase by 10 kW"),
    pytest.param(100, True, 100, id="Increase by 100% (limited by max_output)"),
])
def test_increase_output_parametrized(valid_data, increase_amount, is_percent, expected_output):
    source = EnergySource.create_instance(valid_data)
    
    print(f"\nPoczątkowa moc wyjściowa: {source.get_actual_output()} kW")
    
    percent_increased, amount_increased = source.increase_output(increase_amount, is_percent)
    
    print(f"Wywołano increase_output({increase_amount}, is_percent={is_percent})")
    print(f"Moc wyjściowa po zwiększeniu: {source.get_actual_output()} kW")
    
    assert source.get_actual_output() == pytest.approx(expected_output)
"""


def test_decrease_output(valid_data):
    source = EnergySource.create_instance(valid_data)
    percent, amount = source.decrease_output(10, is_percent=True)
    assert source.actual_output == 45
    assert percent == pytest.approx(10)
    assert amount == pytest.approx(5)


def test_set_output(valid_data):
    source = EnergySource.create_instance(valid_data)
    source.set_output(75)
    assert source.actual_output == 75
    source.set_output(150)  # above max_output
    assert source.actual_output == 100
    source.set_output(5)  # below min_output
    assert source.actual_output == 10


def test_is_at_max_output(valid_data):
    source = EnergySource.create_instance(valid_data)
    assert not source.is_at_max_output()
    source.set_output(100)
    assert source.is_at_max_output()


def test_get_available_capacity(valid_data):
    source = EnergySource.create_instance(valid_data)
    assert source.get_available_capacity() == 50


def test_update_state(valid_data):
    source = EnergySource.create_instance(valid_data)
    new_data = {
        "id": 1,  # Dodaj id
        "name": "Test Source",  # Dodaj name
        "priority": 1,  # Dodaj priority
        "max_output": 100,  # Dodaj max_output
        "min_output": 10,  # Dodaj min_output
        "actual_output": 75,
        "switch_status": True,  # Dodaj switch_status
        "device_status": "offline",
    }
    assert source.update_state(new_data)
    assert source.actual_output == 75
    assert source.device_status == "offline"


def test_try_increase_output(mocker, valid_data):
    source = EnergySource.create_instance(valid_data)
    mocker.patch("time.sleep")  # mock sleep to speed up test
    percent, amount = source.try_increase_output(20, is_percent=True)
    assert source.actual_output == 60
    assert percent == pytest.approx(20)
    assert amount == pytest.approx(10)


def test_try_decrease_output(mocker, valid_data):
    source = EnergySource.create_instance(valid_data)
    mocker.patch("time.sleep")  # mock sleep to speed up test
    percent, amount = source.try_decrease_output(10, is_percent=True)
    assert source.actual_output == 45
    assert percent == pytest.approx(10)
    assert amount == pytest.approx(5)
