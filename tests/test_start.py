from unittest.mock import AsyncMock, patch


def test_start_run_initializes_database_and_runs_bot():
    with patch("database.init_db.init_db") as mock_init_db, patch("src.main.main", new_callable=AsyncMock) as mock_main:
        import start

        with patch("asyncio.run") as mock_asyncio_run:
            start.run()

        coroutine = mock_asyncio_run.call_args.args[0]
        coroutine.close()

        mock_init_db.assert_called_once_with()
        mock_main.assert_called_once_with()
        mock_asyncio_run.assert_called_once()
