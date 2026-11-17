-- The test runner creates and drops its own database (test_baithak, plus suffixes when tests
-- run in parallel), so the app user needs rights on that name pattern as well.
GRANT ALL PRIVILEGES ON `test\_baithak%`.* TO 'baithak'@'%';
