"""Crop the art panel out of the card photos and save a thumbnail per card id.

Artwork belongs to Plaid Hat Games. These crops are for **local use on this machine only**:
`art/` is git-ignored and nothing here may be committed or published.

    uv run python scripts/build_art.py --source-dir <dir> --out art

The mapping below records which photo shows which card; it is built from the transcription
work, not from the file names, because the files arrive with hashed names.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

from PIL import Image

# (relative file name, card id) — recorded when each card was transcribed.
CARD_PHOTOS: Final[tuple[tuple[str, str], ...]] = (
    (
        "f605060b7146998badf1cdc74cc74adb3d39d4180ee125be67cd2c8f47dd33d6/img_396d22db8e87.png",
        "cave_goblins-sneeks",
    ),
    (
        "accf373fbac87b32d6f48d7edc69dcfd95b9f472cbe52855d5383c786c4ee6fe/img_0bafa99d5dfa.png",
        "cave_goblins-enrage_the_horde",
    ),
    (
        "b316e9739c57c8b9c3e070e37f52320f384bd0baec68084a36737efd2d668478/img_e2da66b081dd.png",
        "cave_goblins-blarf",
    ),
    (
        "2bd65a357b109a3627038fc709c5c95952acb25a801f38dd4b216f4ad49bc3c0/img_25ab83ef6b70.png",
        "cave_goblins-smeg",
    ),
    (
        "020e97d4ff79de570ef9fd74e1abd6e7fec1d67eb0b47087433461dc8763f857/img_0e4d8627c2a9.png",
        "cave_goblins-the_eater",
    ),
    (
        "62112f11beeb9294b9f6b3f53a826a4a64e3783b84c7c5fd06c7851a216a33e6/img_5d59bb03b976.png",
        "cave_goblins-unrelenting",
    ),
    (
        "b8713b88283d9f95c5289306203a53de54b34a20701629d21f4015e8ab7841c9/img_00369a659e56.png",
        "cave_goblins-pile_on",
    ),
    (
        "34040fbc816da7ce8a83548f56d0bcae6bd4f8d34c016ac6c92b9595666fc48c/img_3f2870ae2c11.png",
        "cave_goblins-sneak",
    ),
    (
        "0c1ab0d18963ecdc74ab3bd585ce0170639a4ab3815bd63696601ce36a849b61/img_8718c4c7fe84.png",
        "cave_goblins-horde_climber",
    ),
    (
        "94bffaa8014a383e224b87750e9750981ec80411410446a78e29f7f839b36bfe/img_c79d7e9cc7ee.png",
        "cave_goblins-horde_slinger",
    ),
    (
        "b8c5bb1644a01d1bf0eea332eb93dadfb97c02dd981f1e773ba7226fec2675c3/img_41ae27350100.png",
        "cave_goblins-horde_clinger",
    ),
    (
        "1be0cde32aa4616af0ec1c420312e37f5e87486b1e9346073e62d94ac8f18c57/img_60bce333e232.png",
        "cave_goblins-beast_rider",
    ),
    (
        "e3790e092cdda216a4fbba1471c0fea6973dc6007671bf6c318a7eda5933e4cb/img_b5b124ba0e89.png",
        "breakers-taculla",
    ),
    (
        "93b616e78b7952e0d5533e535b5aeabcc6c61397afb154c8994e5645cfb18dab/img_dca821c77afb.png",
        "breakers-mind_control",
    ),
    (
        "18db8722b820067bdb8f8c2d0fe045130e31b1f8c73a572f0eea23eccf12cd5f/img_45af5f416a7b.png",
        "breakers-gwalark",
    ),
    (
        "8fd33af3b348b0eb172442e072d6629491c0c716c5d201200a39fb234e2ee7ce/img_370e3ae7932d.png",
        "breakers-gulldune",
    ),
    (
        "2197d896ed0c3d44cdf7997e600bfc5fec2a18676487300df9e237596ebb84c9/img_d6dc9073cdcd.png",
        "breakers-perplexing_tempest",
    ),
    (
        "42f6813b257bc9d369452529e5c577247862e4951b62c66b5f4f6a13dde9aaed/img_33ec12d339b6.png",
        "breakers-hypnotic_call",
    ),
    (
        "209c667ddb8417cf177feea12b795572a84006db5aa82526ea78285497b4e977/img_d0313b6c7703.png",
        "breakers-blast",
    ),
    (
        "b2bbf47c920d969722d7c764bb5618108360917ea3d6e9b04ebe0bb77bacea1b/img_862475a5fe52.png",
        "breakers-wind_archer",
    ),
    (
        "30ba8b12a4ced136b2ec23865bbb8e42555d5bad9f985faa24cce2989492f103/img_63ce1626bdb3.png",
        "breakers-wind_mage",
    ),
    (
        "057834563f3cfb5e0a68611c76327c266796279a4d5cf0fdfde73313c0678d83/img_e519dfff67a7.png",
        "breakers-mind_witch",
    ),
    (
        "5165ad619d69bb0b205cc0dff428db7405db6ffb76d9c2a1782f788e4c79405b/img_9e8d20bb5400.png",
        "breakers-halal",
    ),
    (
        "42d7e033fcaf8bab5f38600c37c516b840a7f050c692d25af615efda471d518e/img_236bd9526afb.png",
        "breakers-deceiver",
    ),
    (
        "926a93feb5a2c288dfb0b78507c8c625f89b49ccaecc8fc3d3e9cfe9b6eb80a3/img_bb46499425c0.png",
        "fallen_kingdom-ret-talus",
    ),
    (
        "37a2309cabb1fdb25fcb5f0976765fc071ebbf5e778b2b875a5e83b4d7036b71/img_0b98535bf0b9.png",
        "fallen_kingdom-elut_bal",
    ),
    (
        "86cffbb25ed1a0106fdffe1472d4be339526ec11ab69751b517105e79aed0f51/img_b89b5099bdd6.png",
        "fallen_kingdom-gul_dass",
    ),
    (
        "7706745107510fd627d991d0a025041c8c6ae22885eff8a3a3a3ca945f90b9e1/img_6d5bab5d858f.png",
        "fallen_kingdom-hellfire_cultist",
    ),
    (
        "2820a555c5174fa4439a259dc51012c1b9c3d0c7b966942b6b2ddfd333e70e2a/img_4055fd448911.png",
        "fallen_kingdom-undead_archer",
    ),
    (
        "10106946f84772167eb4830d1b60881f9109e2853b9a23715afd59e962711d9a/img_bcaac5bd9a7a.png",
        "fallen_kingdom-undead_carrier",
    ),
    (
        "609415eef924da457e3d49c81addfb2d47a4bb0cde9eda0cffd810c15c548aa4/img_8aac099eed86.png",
        "fallen_kingdom-sacrificial_pyre",
    ),
    (
        "9e6649bc1d7518e650185bb2f8bd911daf84c7a608aa037cfa8b5fd1ae93752e/img_86a0b26ebc77.png",
        "fallen_kingdom-purge",
    ),
    (
        "81d056696f251327d35957c09feae5f439b73c0c91de7f6a06cac38691daa02c/img_97db73b5a295.png",
        "fallen_kingdom-hellforged_weapon",
    ),
    (
        "d028bba2d0cb8af8fcb9fefdf4ba3765c469e4065133af22a17a494abc07ecda/img_d69399e1f91e.png",
        "fallen_kingdom-blood_summon",
    ),
    (
        "548bc3766ad37136282d28e12a150d278b5e9cb4ce6686a6112f44326eee63aa/img_fab3711c51a1.png",
        "fallen_kingdom-dragos",
    ),
    (
        "b61138a31b70d44d10e9bd8cb06d2f2cd04adec70e04be45ff33fd9f8e9a863e/img_21a338384b93.png",
        "fallen_kingdom-undead_warrior",
    ),
)

# The art panel is the right-hand portion of the card, below the name banner.
ART_BOX = (0.47, 0.10, 0.99, 0.97)
THUMB_WIDTH = 180


def crop_art(image: Image.Image) -> Image.Image:
    width, height = image.size
    left, top, right, bottom = ART_BOX
    box = (int(width * left), int(height * top), int(width * right), int(height * bottom))
    panel = image.crop(box)
    ratio = THUMB_WIDTH / panel.width
    return panel.resize((THUMB_WIDTH, max(1, int(panel.height * ratio))), Image.Resampling.LANCZOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default="~/.hermes/cache/documents/native-inputs")
    parser.add_argument("--out", default="art")
    args = parser.parse_args()

    source = Path(args.source_dir).expanduser()
    destination = Path(args.out)
    destination.mkdir(parents=True, exist_ok=True)

    made = 0
    missing = 0
    for relative, card_id in CARD_PHOTOS:
        path = source / relative
        if not path.exists():
            print(f"missing photo: {relative}")
            missing += 1
            continue
        with Image.open(path) as image:
            thumb = crop_art(image.convert("RGB"))
        thumb.save(destination / f"{card_id}.png")
        made += 1

    print(f"wrote {made} thumbnails to {destination}/ ({missing} photos not found)")
    print("art/ is git-ignored: this artwork belongs to Plaid Hat Games and stays local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
