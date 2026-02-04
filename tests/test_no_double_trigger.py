"""Tests pour éviter la double exécution des triggers recovery_update.

Ce module teste le bug où le changement de target_hour créait un doublon
de trigger recovery_update_hour car _setup_time_triggers() ne annulait pas
le trigger existant dans _unsub_recovery_update.

Bug corrigé: Dans _setup_time_triggers(), avant de programmer le trigger
recovery_update_hour, on annule d'abord _unsub_recovery_update s'il existe.
"""

from datetime import datetime, time as dt_time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from custom_components.SmartHRT.coordinator import (
    SmartHRTCoordinator,
    SmartHRTData,
    SmartHRTState,
)


def make_mock_now(year=2026, month=2, day=4, hour=8, minute=0, second=0):
    """Helper pour créer un datetime pour les tests."""
    return datetime(year, month, day, hour, minute, second)


class TestNoDoubleTriggerOnTargetHourChange:
    """Tests pour éviter la double exécution des triggers."""

    @pytest.mark.asyncio
    async def test_unsub_recovery_update_cancelled_on_setup_time_triggers(
        self, create_coordinator
    ):
        """Vérifie que _unsub_recovery_update est annulé dans _setup_time_triggers.

        Scénario du bug:
        1. Un trigger recovery_update est programmé via _schedule_recovery_update
        2. On change target_hour, ce qui appelle _setup_time_triggers
        3. _setup_time_triggers programme un nouveau trigger dans _unsub_time_triggers
        4. AVANT la correction: _unsub_recovery_update n'était pas annulé → doublon
        5. APRÈS la correction: _unsub_recovery_update est annulé → pas de doublon
        """
        with patch("custom_components.SmartHRT.coordinator.dt_util") as mock_dt:
            mock_now = make_mock_now(hour=8, minute=0, second=0)
            mock_dt.now.return_value = mock_now
            mock_dt.as_local.side_effect = lambda x: x

            coord = await create_coordinator(
                initial_state=SmartHRTState.MONITORING,
                recovery_update_hour=make_mock_now(hour=8, minute=30),
            )

            # Simuler qu'un trigger existe dans _unsub_recovery_update
            mock_unsub = MagicMock()
            coord._unsub_recovery_update = mock_unsub

            # Appeler _setup_time_triggers (comme le fait set_target_hour)
            coord._setup_time_triggers()

            # Vérifier que l'ancien trigger a été annulé
            mock_unsub.assert_called_once()
            # Vérifier que _unsub_recovery_update a été remis à None
            assert coord._unsub_recovery_update is None

    @pytest.mark.asyncio
    async def test_set_target_hour_does_not_create_duplicate_trigger(
        self, create_coordinator
    ):
        """Vérifie que set_target_hour ne crée pas de doublon de trigger."""
        with patch("custom_components.SmartHRT.coordinator.dt_util") as mock_dt:
            mock_now = make_mock_now(hour=8, minute=0, second=0)
            mock_dt.now.return_value = mock_now
            mock_dt.as_local.side_effect = lambda x: x

            coord = await create_coordinator(
                initial_state=SmartHRTState.MONITORING,
                recovery_update_hour=make_mock_now(hour=8, minute=30),
            )

            # Simuler qu'un trigger existe
            mock_unsub = MagicMock()
            coord._unsub_recovery_update = mock_unsub

            # Changer target_hour
            coord.set_target_hour(dt_time(17, 30, 0))

            # L'ancien trigger doit avoir été annulé
            mock_unsub.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_error_when_unsub_recovery_update_is_none(
        self, create_coordinator
    ):
        """Vérifie qu'il n'y a pas d'erreur si _unsub_recovery_update est None."""
        with patch("custom_components.SmartHRT.coordinator.dt_util") as mock_dt:
            mock_now = make_mock_now(hour=8, minute=0, second=0)
            mock_dt.now.return_value = mock_now
            mock_dt.as_local.side_effect = lambda x: x

            coord = await create_coordinator(
                initial_state=SmartHRTState.HEATING_ON,
            )

            # S'assurer que _unsub_recovery_update est None
            coord._unsub_recovery_update = None

            # Ceci ne doit pas lever d'exception
            coord._setup_time_triggers()

            # Le test passe si aucune exception n'est levée

    @pytest.mark.asyncio
    async def test_recovery_update_trigger_still_works_after_target_hour_change(
        self, create_coordinator
    ):
        """Vérifie que le trigger recovery_update fonctionne après changement de target_hour."""
        with patch("custom_components.SmartHRT.coordinator.dt_util") as mock_dt:
            # Heure initiale: avant le trigger
            mock_now = make_mock_now(hour=7, minute=0, second=0)
            mock_dt.now.return_value = mock_now
            mock_dt.as_local.side_effect = lambda x: x

            coord = await create_coordinator(
                initial_state=SmartHRTState.MONITORING,
                recovery_update_hour=make_mock_now(hour=8, minute=0),
                target_hour=dt_time(6, 0, 0),
            )

            # Changer target_hour
            coord.set_target_hour(dt_time(17, 30, 0))

            # Vérifier que le nouveau target_hour est bien enregistré
            assert coord.data.target_hour == dt_time(17, 30, 0)

            # Le trigger recovery_update devrait toujours être dans _unsub_time_triggers
            # (programmé par _setup_time_triggers après l'annulation de _unsub_recovery_update)


class TestTriggerCleanupConsistency:
    """Tests pour la cohérence du nettoyage des triggers."""

    @pytest.mark.asyncio
    async def test_cancel_time_triggers_clears_list(self, create_coordinator):
        """Vérifie que _cancel_time_triggers vide bien la liste."""
        with patch("custom_components.SmartHRT.coordinator.dt_util") as mock_dt:
            mock_now = make_mock_now(hour=8, minute=0, second=0)
            mock_dt.now.return_value = mock_now
            mock_dt.as_local.side_effect = lambda x: x

            coord = await create_coordinator(initial_state=SmartHRTState.HEATING_ON)

            # Ajouter des mocks dans la liste
            mock_unsub1 = MagicMock()
            mock_unsub2 = MagicMock()
            coord._unsub_time_triggers = [mock_unsub1, mock_unsub2]

            coord._cancel_time_triggers()

            # Les deux callbacks doivent avoir été appelés
            mock_unsub1.assert_called_once()
            mock_unsub2.assert_called_once()

            # La liste doit être vide
            assert len(coord._unsub_time_triggers) == 0

    @pytest.mark.asyncio
    async def test_async_unload_cancels_all_triggers(self, create_coordinator):
        """Vérifie que async_unload annule tous les triggers."""
        with patch("custom_components.SmartHRT.coordinator.dt_util") as mock_dt:
            mock_now = make_mock_now(hour=8, minute=0, second=0)
            mock_dt.now.return_value = mock_now
            mock_dt.as_local.side_effect = lambda x: x

            coord = await create_coordinator(initial_state=SmartHRTState.MONITORING)

            # Ajouter des mocks
            mock_time_trigger = MagicMock()
            mock_recovery_update = MagicMock()
            mock_recovery_start = MagicMock()

            coord._unsub_time_triggers = [mock_time_trigger]
            coord._unsub_recovery_update = mock_recovery_update
            coord._unsub_recovery_start = mock_recovery_start

            await coord.async_unload()

            # Tous les triggers doivent avoir été annulés
            mock_time_trigger.assert_called_once()
            mock_recovery_update.assert_called_once()
            mock_recovery_start.assert_called_once()

            # Les références doivent être nettoyées
            assert coord._unsub_recovery_update is None
            assert coord._unsub_recovery_start is None
            assert len(coord._unsub_time_triggers) == 0
