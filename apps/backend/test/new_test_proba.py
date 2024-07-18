import pytest
from unittest.mock import Mock, patch
from apps.backend.managment.deficit_action import DeficitAction
from apps.backend.managment.energy_deficit_manager import EnergyDeficitManager


@pytest.fixture
def mock_microgrid():
    microgrid = Mock()
    microgrid.get_active_devices.return_value = []
    microgrid.get_inactive_devices.return_value = []
    microgrid.bess_units = []
    microgrid.is_bess_available.return_value = False
    return microgrid


@pytest.fixture
def mock_osd():
    osd = Mock()
    osd.get_bought_power.return_value = 0
    osd.get_purchase_limit.return_value = 1000
    return osd


@pytest.fixture
def energy_deficit_manager(mock_microgrid, mock_osd):
    return EnergyDeficitManager(mock_microgrid, mock_osd)


def test_handle_deficit_increase_active_devices(energy_deficit_manager, mock_microgrid):
    mock_device = Mock()
    mock_device.is_at_full_capacity.return_value = False
    mock_device.increase_output_to_full_capacity.return_value = 100
    mock_microgrid.get_active_devices.return_value = [mock_device]

    result = energy_deficit_manager.handle_deficit(150)

    assert result["amount_managed"] == 100
    assert result["remaining_deficit"] == 50


def test_handle_deficit_activate_inactive_devices(
    energy_deficit_manager, mock_microgrid
):
    mock_device = Mock()
    mock_device.try_activate.return_value = True
    mock_device.increase_output_to_full_capacity.return_value = 200
    mock_microgrid.get_inactive_devices.return_value = [mock_device]

    result = energy_deficit_manager.handle_deficit(150)

    assert result["amount_managed"] == 150
    assert result["remaining_deficit"] == 0


def test_handle_deficit_discharge_bess(energy_deficit_manager, mock_microgrid):
    mock_bess = Mock()
    mock_bess.get_switch_status.return_value = True
    mock_bess.get_charge_level.return_value = 300
    mock_bess.discharge.return_value = 150
    mock_microgrid.bess_units = [mock_bess]
    mock_microgrid.is_bess_available.return_value = True

    result = energy_deficit_manager.handle_deficit(150)

    assert result["amount_managed"] == 150
    assert result["remaining_deficit"] == 0


def test_handle_deficit_buy_energy(energy_deficit_manager, mock_osd):
    mock_osd.buy_power.return_value = True

    result = energy_deficit_manager.handle_deficit(150)

    assert result["amount_managed"] == 150
    assert result["remaining_deficit"] == 0
    mock_osd.buy_power.assert_called_once_with(150)


def test_handle_deficit_limit_consumption(energy_deficit_manager, mock_microgrid):
    mock_microgrid.get_total_consumption.return_value = 200
    mock_microgrid.reduce_consumption.return_value = True

    result = energy_deficit_manager.handle_deficit(150)

    assert result["amount_managed"] == 150
    assert result["remaining_deficit"] == 0
    mock_microgrid.reduce_consumption.assert_called_once_with(150)


def test_handle_deficit_multiple_actions(
    energy_deficit_manager, mock_microgrid, mock_osd
):
    # Setup mocks for multiple actions
    mock_active_device = Mock()
    mock_active_device.is_at_full_capacity.return_value = False
    mock_active_device.increase_output_to_full_capacity.return_value = 50
    mock_microgrid.get_active_devices.return_value = [mock_active_device]

    mock_inactive_device = Mock()
    mock_inactive_device.try_activate.return_value = True
    mock_inactive_device.increase_output_to_full_capacity.return_value = 75
    mock_microgrid.get_inactive_devices.return_value = [mock_inactive_device]

    mock_osd.buy_power.return_value = True

    result = energy_deficit_manager.handle_deficit(200)

    assert result["amount_managed"] == 200
    assert result["remaining_deficit"] == 0
    assert mock_active_device.increase_output_to_full_capacity.called
    assert mock_inactive_device.try_activate.called
    assert mock_osd.buy_power.called
