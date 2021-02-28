import pygame

pygame.mixer.init()
pygame.mixer.music.load("/home/an/app/bgm/初弦__ - 「铅封行动」主界面.mp3")
while True:
    if pygame.mixer.music.get_busy()==False:
        pygame.mixer.music.play()