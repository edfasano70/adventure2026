#!/usr/bin/env python3
import pygame
pygame.init()

CELL    =   32  #80
HERO    =   20  #40
WIDTH   =   640 #1280
HEIGHT  =   480 #720

class LandingPage(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.image.load('adventure_intro.png').convert_alpha()
        self.rect=self.image.get_rect()



gameScreen  =   pygame.display.set_mode((WIDTH,HEIGHT))
pygame.display.set_caption('Adventure 2 - FanMade')
pygame_icon = pygame.image.load('atari_icon_32.png')
pygame.display.set_icon(pygame_icon)

intro=Banner()

gameOver = False
while not gameOver:

    #-----------FONDO---------------
    gameScreen.fill('black')

    #----------DIBUJO--------
    listIntro=   pygame.sprite.Group()
    intro.rect.x=0
    intro.rect.y=0
    listIntro.add(intro)
    listIntro.draw(gameScreen)
    # for row in maps[currentMap][1]:
    #     for cell in row:
    #         if cell == 'X':
    #             wall.rect.x =   x
    #             wall.rect.y =   y
    #             listWall.add(wall)
    #             listWall.draw(gameScreen)
    #         else:
    #             grass.rect.x = x
    #             grass.rect.y = y
    #             listGrass.add(grass)
    #             listGrass.draw(gameScreen)
    #         x += CELL
    #     x =  0
    #     y += CELL
    
    # listHero.draw(gameScreen)
    # #map_draw(gameScreen,listWalls)
    pygame.display.flip()
pygame.quit()

        
