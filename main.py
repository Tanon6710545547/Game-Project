"""
Kiritoo - Roguelike Tower-Climbing Game
Entry point
"""
import pygame
import sys
from src.game import Game

def main():
    pygame.init()
    pygame.mixer.init()
    game = Game()
    try:
        game.run()
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()
