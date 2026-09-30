"""Fictional-entity fact generator (P1-02).

Entities are invented from syllables so that answers cannot come from a model's
memory. Only the given context can support them, which is what faithfulness and
abstention need to measure.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

SYLLABLES = [("سا", "sa"), ("لو", "lu"), ("مي", "mi"), ("را", "ra"), ("نو", "nu"), ("كا", "ka"),
             ("دي", "di"), ("فو", "fu"), ("زا", "za"), ("تي", "ti"), ("با", "ba"), ("هو", "hu"),
             ("جي", "ji"), ("ما", "ma"), ("ري", "ri"), ("شا", "sha"), ("قو", "qu"), ("وا", "wa"),
             ("لي", "li"), ("نا", "na"), ("طو", "tu"), ("غا", "gha")]
ENDINGS = [("", ""), ("ن", "n"), ("ر", "r"), ("ل", "l"), ("س", "s")]
PRODUCTS = ["التمر", "القهوة", "الزيتون", "العسل", "الملح", "القطن", "الحرير", "الفخار", "الزعفران", "الورق", "الصابون", "النحاس"]
FIRST_NAMES = [("سالم", "Salem"), ("مريم", "Maryam"), ("خالد", "Khaled"), ("ليلى", "Layla"), ("يوسف", "Yousef"),
               ("هدى", "Huda"), ("عمر", "Omar"), ("نورة", "Noura"), ("فهد", "Fahad"), ("سلمى", "Salma")]


@dataclass(frozen=True)
class Name:
    ar: str
    lat: str


def fictional_name(rng: random.Random, syllables: int = 3) -> Name:
    parts = [rng.choice(SYLLABLES) for _ in range(syllables)]
    end = rng.choice(ENDINGS)
    ar = "".join(p[0] for p in parts) + end[0]
    lat = "".join(p[1] for p in parts) + end[1]
    return Name(ar, lat.capitalize())


@dataclass(frozen=True)
class Town:
    name: Name
    river: Name
    year: int
    population: int
    product: str
    mayor: Name

    # attribute -> (sentence template, gold value(s))
    def sentence(self, attr: str) -> str:
        n = self.name.ar
        return {
            "river": f"تقع بلدة {n} على ضفاف نهر {self.river.ar}.",
            "year": f"تأسست بلدة {n} عام {self.year}.",
            "population": f"يبلغ عدد سكان بلدة {n} {self.population} نسمة.",
            "product": f"أشهر منتجات بلدة {n} هو {self.product}.",
            "mayor": f"رئيس بلدية {n} الحالي هو {self.mayor.ar}.",
        }[attr]

    def gold(self, attr: str) -> list[str]:
        return {
            "river": [self.river.ar, self.river.lat],
            "year": [str(self.year)],
            "population": [str(self.population)],
            "product": [self.product, self.product.removeprefix("ال")],
            "mayor": [self.mayor.ar, self.mayor.lat],
        }[attr]


ATTRS = ("river", "year", "population", "product", "mayor")

QUESTIONS_MSA = {
    "river": "على ضفاف أي نهر تقع بلدة {n}؟",
    "year": "في أي عام تأسست بلدة {n}؟",
    "population": "كم يبلغ عدد سكان بلدة {n}؟",
    "product": "ما أشهر منتجات بلدة {n}؟",
    "mayor": "من رئيس بلدية {n} الحالي؟",
}


def make_town(rng: random.Random) -> Town:
    first = rng.choice(FIRST_NAMES)
    family = fictional_name(rng, 2)
    mayor = Name(f"{first[0]} {family.ar}", f"{first[1]} {family.lat}")
    return Town(
        name=fictional_name(rng, 3),
        river=fictional_name(rng, 2),
        year=rng.randint(1200, 1950),
        population=rng.randint(1_200, 950_000),
        product=rng.choice(PRODUCTS),
        mayor=mayor,
    )


def distinct_towns(rng: random.Random, k: int) -> list[Town]:
    towns: list[Town] = []
    while len(towns) < k:
        t = make_town(rng)
        if all(t.name.ar != o.name.ar and t.river.ar != o.river.ar and t.product != o.product and t.year != o.year
               for o in towns):
            towns.append(t)
    return towns
