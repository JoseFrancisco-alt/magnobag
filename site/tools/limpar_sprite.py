"""Transforma a foto (JPG borrado) de um sprite em pixel art limpa, com fundo transparente.

1. Descobre o tamanho do "pixel" do sprite na foto (o que deixa cada bloco com a cor mais uniforme).
2. Pega a cor mediana de cada bloco, o que apaga o borrado do JPG.
3. Blocos quase brancos viram transparentes (o fundo).
4. Recorta as bordas vazias e salva pequeno; o site amplia sem borrar.

Uso: python site/tools/limpar_sprite.py foto.jpg site/static/mascote.png
"""
import sys

import numpy as np
from PIL import Image


def melhor_grade(img):
    """Testa tamanhos e deslocamentos de bloco e fica com o que dá menos variação dentro dos blocos."""
    cinza = img.mean(axis=2)
    melhor = None
    for tam in np.arange(8, 20.01, 0.25):
        for dx in np.arange(0, tam, 1.0):
            for dy in np.arange(0, tam, 1.0):
                xs = np.arange(dx, cinza.shape[1] - tam, tam)
                ys = np.arange(dy, cinza.shape[0] - tam, tam)
                # amostra o miolo de cada bloco: se a grade está certa, o miolo é de uma cor só
                cx = (xs + tam * 0.3).astype(int), (xs + tam * 0.7).astype(int)
                cy = (ys + tam * 0.3).astype(int), (ys + tam * 0.7).astype(int)
                a = cinza[np.ix_(cy[0], cx[0])]
                b = cinza[np.ix_(cy[1], cx[1])]
                c = cinza[np.ix_(cy[0], cx[1])]
                d = cinza[np.ix_(cy[1], cx[0])]
                erro = (np.abs(a - b) + np.abs(a - c) + np.abs(a - d)).mean()
                if melhor is None or erro < melhor[0]:
                    melhor = (erro, tam, dx, dy)
    return melhor


def main(entrada, saida):
    img = np.asarray(Image.open(entrada).convert("RGB")).astype(float)
    erro, tam, dx, dy = melhor_grade(img)
    print(f"bloco de {tam:.2f}px (deslocamento {dx:.0f},{dy:.0f}), erro {erro:.1f}")

    colunas = int((img.shape[1] - dx) // tam)
    linhas = int((img.shape[0] - dy) // tam)
    sprite = np.zeros((linhas, colunas, 4), dtype=np.uint8)
    for j in range(linhas):
        for i in range(colunas):
            x0, y0 = dx + i * tam, dy + j * tam
            m = int(tam * 0.25)  # ignora a beirada do bloco, onde o JPG mistura cores
            bloco = img[int(y0) + m:int(y0 + tam) - m, int(x0) + m:int(x0 + tam) - m]
            cor = np.median(bloco.reshape(-1, 3), axis=0)
            fundo = cor.min() > 225  # quase branco = fundo
            sprite[j, i] = (*cor.round().astype(np.uint8), 0 if fundo else 255)

    # recorta as bordas transparentes, deixando 1 pixel de folga
    opacos = np.argwhere(sprite[:, :, 3] > 0)
    (y0, x0), (y1, x1) = opacos.min(axis=0), opacos.max(axis=0)
    sprite = sprite[max(y0 - 1, 0):y1 + 2, max(x0 - 1, 0):x1 + 2]
    Image.fromarray(sprite, "RGBA").save(saida)
    print(f"sprite de {sprite.shape[1]}x{sprite.shape[0]} pixels salvo em {saida}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
