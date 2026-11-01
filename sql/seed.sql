-- Seed demo accounts
-- Passwords generated with werkzeug.security.generate_password_hash
-- Admin: login=Conf2027, password=Demo77
-- Client: login=client01, password=ClientPass123!

INSERT INTO users (login, password_hash, full_name, phone, email, role) VALUES
(
    'Conf2027',
    'pbkdf2:sha256:600000$YwMlRSZCGYcxPOqp$d9c14a2f7ef4b2dfd3de89ee3bdf3eeb8b1a7f85bd2a48a47e4e6aba69f5ddeb',
    'Администратор Системы',
    '8(900)000-00-01',
    'admin@booking2027.ru',
    'admin'
),
(
    'client01',
    'pbkdf2:sha256:600000$XkJmNpVBTRqzHyAd$a7c89f3e1b2d4c6e8f0a2b4c6d8e0f1a3b5c7d9e1f3a5b7c9d1e3f5a7b9c1d3',
    'Иванов Иван Иванович',
    '8(901)123-45-67',
    'client01@example.ru',
    'user'
);

-- Seed venues
INSERT INTO venues (name, type, capacity, price_per_hour) VALUES
('Аудитория 101',   'аудитория', 30,  500.00),
('Коворкинг Центр', 'коворкинг', 50, 1200.00),
('Кинозал «Свет»',  'кинозал',  100, 2500.00);
