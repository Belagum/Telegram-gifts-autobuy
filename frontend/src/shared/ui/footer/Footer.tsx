// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import "./footer.css";

const GithubIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
  </svg>
);

const TelegramIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
    <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
  </svg>
);

const HeartIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
  </svg>
);

export const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="footer">
      <div className="footer__container">
        <div className="footer__grid">
          {/* О проекте */}
          <div className="footer__section">
            <h3 className="footer__title">GiftBuyer</h3>
            <p className="footer__description">
              Автоматическая покупка подарков в Telegram. Быстро, удобно, надежно.
            </p>
            <div className="footer__social">
              <a 
                href="https://github.com/Belagum" 
                target="_blank" 
                rel="noopener noreferrer"
                className="footer__social-link"
                title="GitHub"
              >
                <GithubIcon />
              </a>
              <a 
                href="https://t.me/ru_nl" 
                target="_blank" 
                rel="noopener noreferrer"
                className="footer__social-link"
                title="Telegram"
              >
                <TelegramIcon />
              </a>
            </div>
          </div>

          {/* Быстрые ссылки */}
          <div className="footer__section">
            <h4 className="footer__subtitle">Навигация</h4>
            <ul className="footer__links">
              <li><a href="/">Главная</a></li>
              <li><a href="/gifts">Подарки</a></li>
              <li><a href="/settings">Настройки</a></li>
            </ul>
          </div>

          {/* Информация */}
          <div className="footer__section">
            <h4 className="footer__subtitle">Информация</h4>
            <ul className="footer__links">
              <li><a href="https://github.com/Belagum/Telegram-gifts-autobuy?tab=readme-ov-file#readme" target="_blank" rel="noopener noreferrer">Документация</a></li>
              <li><a href="https://github.com/Belagum/Telegram-gifts-autobuy/issues" target="_blank" rel="noopener noreferrer">Сообщить о проблеме</a></li>
              <li><a href="https://github.com/Belagum/Telegram-gifts-autobuy" target="_blank" rel="noopener noreferrer">Исходный код</a></li>
            </ul>
          </div>

          {/* Поддержка */}
          <div className="footer__section">
            <h4 className="footer__subtitle">Поддержка</h4>
            <ul className="footer__links">
              <li><a href="https://t.me/ru_nl" target="_blank" rel="noopener noreferrer">Связаться</a></li>
              <li><a href="https://github.com/Belagum/Telegram-gifts-autobuy" target="_blank" rel="noopener noreferrer">GitHub</a></li>
            </ul>
          </div>
        </div>

        <div className="footer__bottom">
          <div className="footer__copyright">
            <p>© {currentYear} GiftBuyer. Все права защищены.</p>
            <p className="footer__made-with">
              Сделано с <HeartIcon /> by <a href="https://github.com/Belagum" target="_blank" rel="noopener noreferrer">Vova</a>
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};

