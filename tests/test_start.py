from unittest.mock import AsyncMock, patch


def test_start_run_runs_bot_without_sync_database_init():
    with patch("src.main.main", new_callable=AsyncMock) as mock_main:
        import start

        with patch("asyncio.run") as mock_asyncio_run:
            start.run()

        coroutine = mock_asyncio_run.call_args.args[0]
        coroutine.close()

        mock_main.assert_called_once_with()
        mock_asyncio_run.assert_called_once()
