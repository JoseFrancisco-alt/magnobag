"""Gera a pixel art do mascote (Mimikyu) a partir de formas simples.

Rasteriza cabeça, pano, orelhas e rabo num grid 28x28, sombreia o lado direito e contorna tudo
de preto, como um sprite de jogo. Rode e cole a saída em DESENHO, no static/mascote.js:

    python site/tools/gerar_mascote.py
"""
import sys

N = 28


def dentro_poligono(x, y, pts):
    d = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            d = not d
        j = i
    return d


def perto_segmentos(x, y, pts, larg):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        if ((x1 + t * dx - x) ** 2 + (y1 + t * dy - y) ** 2) ** .5 <= larg:
            return True
    return False


def cabeca(x, y):
    return ((x - 12.5) / 6.9) ** 2 + ((y - 10.4) / 5.7) ** 2 <= 1


CORPO = [(7.0, 13.6), (18.0, 13.6), (20.2, 19.5), (21.2, 25), (19.2, 23.8), (17.2, 25), (15.2, 23.8), (13.2, 25),
         (11.2, 23.8), (9.2, 25), (7.2, 23.8), (5.0, 25), (4.8, 19.5)]
ORELHA_ESQ = [(5.0, 9.4), (11.4, 5.0), (7.4, 0.2), (4.2, 0.8)]
ORELHA_DIR = [(13.8, 5.4), (19.2, 7.8), (20.4, 6.0), (23.4, 9.4), (25.8, 8.4), (22.4, 3.4), (18.6, 1.6), (15.8, 2.4)]
RABO = [(18.6, 21.6), (22.2, 18.6), (20.8, 17.6), (24.4, 14.6), (23.0, 13.8), (26.0, 11.8)]


def gerar():
    g = [["." for _ in range(N)] for _ in range(N)]
    for y in range(N):
        for x in range(N):
            px, py = x + .5, y + .5
            if perto_segmentos(px, py, RABO, .85):
                g[y][x] = "b" if x >= 22 else "B"
            if cabeca(px, py) or dentro_poligono(px, py, CORPO):
                limite = 16.9 if py < 15.5 else 15.6 + (py - 15) * 0.45  # sombra acompanha o pano abrindo
                g[y][x] = "S" if px > limite else "Y"
                if py > 22.6:
                    g[y][x] = "D"
            if dentro_poligono(px, py, ORELHA_ESQ):
                g[y][x] = "E" if py < 3.2 else "Y"
            if dentro_poligono(px, py, ORELHA_DIR):
                g[y][x] = "E" if px > 22.2 else ("S" if px > 19 else "Y")

    # contorno: vazio encostado (4 vizinhos) em algo pintado
    pintado = {(x, y) for y in range(N) for x in range(N) if g[y][x] != "."}
    for y in range(N):
        for x in range(N):
            if g[y][x] == "." and any((x + dx, y + dy) in pintado for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                g[y][x] = "O"

    # rosto rabiscado
    for x, y, c in [(9, 9, "K"), (10, 9, "K"), (9, 10, "K"), (10, 10, "K"),
                    (15, 9, "K"), (16, 9, "K"), (15, 10, "K"), (16, 10, "K"),
                    (7, 12, "R"), (8, 12, "R"), (17, 12, "R"), (18, 12, "R")]:
        g[y][x] = c
    # olhinhos de quem está embaixo do pano, espiando na barra
    for x, y in [(10, 25), (14, 25)]:
        if g[y][x] == "O":
            g[y][x] = "W"
    return ["".join(linha) for linha in g]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for linha in gerar():
        print(f'    "{linha}",')
