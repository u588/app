flag = True
while flag:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            flag = False