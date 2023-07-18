import pygame
from settings import *
from entity import Entity
from level import *
from BPlusTree import *
from support import *
import support
import heapq


def astar(start, goal):
    open_list = []
    closed_list = []

    heapq.heappush(open_list, start)

    while len(open_list) > 0:
        current_node = heapq.heappop(open_list)

        if current_node.position == goal.position:
            path = []
            while current_node is not None:
                path.append(current_node.position)
                current_node = current_node.parent
            return path[::-1]  # Reverse the path to get the correct order

        closed_list.append(current_node)

        # Generate the neighboring nodes
        neighbors = []
        for direction in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor_position = (current_node.position[0] + direction[0], current_node.position[1] + direction[1])
            neighbors.append(Node(neighbor_position, current_node))

        for neighbor in neighbors:
            if neighbor in closed_list:
                continue

            neighbor.g = current_node.g + 1
            neighbor.h = heuristic(neighbor, goal)
            neighbor.f = neighbor.g + neighbor.h

            if neighbor not in open_list:
                heapq.heappush(open_list, neighbor)
            elif neighbor.g >= current_node.g:
                continue



class Enemy(Entity):
    def __init__(self, monster_name, pos, groups, obstacle_sprites, damage_player,
                 trigger_death_particles, add_exp,state):

        # general setup
        super().__init__(groups)
        self.sprite_type = 'enemy'
        self.game_state = state;
        # graphics setup
        self.import_graphics(monster_name)
        self.status = 'idle'
        self.image = self.animations[self.status][self.frame_index]

        # movement
        self.rect = self.image.get_rect(topleft=pos)
        self.hitbox = self.rect.inflate(0, -10)
        self.obstacle_sprites = obstacle_sprites
        # self.trap_sprites = trap_sprites

        # stats
        self.monster_name = monster_name
        monster_info = monster_data[self.monster_name]
        self.health = monster_info['health']
        self.INITIAL_health = monster_info['health']
        self.INITIAL_notice_radius = monster_info['notice_radius']
        self.exp = monster_info['exp']
        self.speed = monster_info['speed']
        self.attack_damage = monster_info['damage']
        self.resistance = monster_info['resistance']
        self.attack_radius = monster_info['attack_radius']
        self.notice_radius = monster_info['notice_radius']
        self.attack_type = monster_info['attack_type']

        # player interaction
        self.can_attack = True
        self.attack_time = None
        self.attack_cooldown = 400
        self.damage_player = damage_player
        self.trigger_death_particles = trigger_death_particles
        self.add_exp = add_exp

        # invincibility timer
        self.vulnerable = True
        self.hit_time = None
        self.invincibility_duration = 300

        # sounds
        self.death_sound = pygame.mixer.Sound('../audio/death.wav')
        self.hit_sound = pygame.mixer.Sound('../audio/hit.wav')
        self.attack_sound = pygame.mixer.Sound(monster_info['attack_sound'])
        self.death_sound.set_volume(0.6)
        self.hit_sound.set_volume(0.6)
        self.attack_sound.set_volume(0.6)

    def import_graphics(self, name):
        self.animations = {'idle': [], 'move': [], 'attack': []}
        main_path = f'../graphics/monsters/{name}/'
        for animation in self.animations.keys():
            self.animations[animation] = import_folder(main_path + animation)

    def get_player_distance_direction(self, player):
        enemy_vec = pygame.math.Vector2(self.rect.center)
        player_vec = pygame.math.Vector2(player.rect.center)
        distance = (player_vec - enemy_vec).magnitude()

        if distance > 0:
            direction = (player_vec - enemy_vec).normalize()
        else:
            direction = pygame.math.Vector2()

        return (distance, direction)

    def get_status(self, player):
        distance = self.get_player_distance_direction(player)[0]
        b_plus_tree = BPlusTree()

        # 插入血量和怪物行为的键值对
        b_plus_tree.insert(30, 0.5)
        b_plus_tree.insert(70, 1)
        b_plus_tree.insert(100, 1.5)

        # 根据怪物血量控制怪物行为
        health_percentage = self.health/self.INITIAL_health * 100
        # if health_percentage != 100:
        #     print(health_percentage)
        behavior = b_plus_tree.search(health_percentage)
        # print(behavior)
        self.notice_radius = self.INITIAL_notice_radius*behavior
        if distance <= self.attack_radius and self.can_attack:
            if self.status != 'attack':
                self.frame_index = 0
            self.status = 'attack'
        elif distance <= self.notice_radius:
            self.status = 'move'
        else:
            self.status = 'idle'

    def actions(self, player):
        if self.status == 'attack':
            self.attack_time = pygame.time.get_ticks()
            self.damage_player(self.attack_damage, self.attack_type)
            self.attack_sound.play()
        elif self.status == 'move':
            self.direction = self.get_player_distance_direction(player)[1]
        else:
            self.direction = pygame.math.Vector2()

    def animate(self):
        animation = self.animations[self.status]

        self.frame_index += self.animation_speed
        if self.frame_index >= len(animation):
            if self.status == 'attack':
                self.can_attack = False
            self.frame_index = 0

        self.image = animation[int(self.frame_index)]
        self.rect = self.image.get_rect(center=self.hitbox.center)

        if not self.vulnerable:
            alpha = self.wave_value()
            self.image.set_alpha(alpha)
        else:
            self.image.set_alpha(255)

    def cooldowns(self):
        current_time = pygame.time.get_ticks()
        if not self.can_attack:
            if current_time - self.attack_time >= self.attack_cooldown:
                self.can_attack = True

        if not self.vulnerable:
            if current_time - self.hit_time >= self.invincibility_duration:
                self.vulnerable = True

    def get_damage(self, player, attack_type):
        if self.vulnerable:
            self.hit_sound.play()
            self.direction = self.get_player_distance_direction(player)[1]
            if attack_type == 'weapon':
                self.health -= player.get_full_weapon_damage()
            else:
                self.health -= player.get_full_bullet_damage()
            self.hit_time = pygame.time.get_ticks()
            self.vulnerable = False

    def check_death(self):
        if self.health <= 0:
            self.kill()
            modify_variable()
            print(support.kill_number)
            self.trigger_death_particles(self.rect.center, self.monster_name)
            self.add_exp(self.exp)
            self.death_sound.play()
            if self.monster_name == 'raccoon':
                self.game_state()



    def hit_reaction(self):
        if not self.vulnerable:
            self.direction *= -self.resistance

    def update(self):
        self.hit_reaction()
        self.move(self.speed)
        self.animate()
        self.cooldowns()
        self.check_death()

    def enemy_update(self, player):
        self.get_status(player)
        self.actions(player)
