-- Create the travis user and grant all privileges for testing
CREATE USER IF NOT EXISTS 'travis'@'%';
GRANT ALL PRIVILEGES ON *.* TO 'travis'@'%';
FLUSH PRIVILEGES;
