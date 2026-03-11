"""
CRITICAL LAYER — Saf Python kodu, LLM yok!
Extraction Agent çıktısını 4 adımda doğrular.
"""

import re
from typing import List, Tuple
from dataclasses import dataclass, field

# ─── Sabitler ────────────────────────────────────────────────────────────────

VALID_ENTITY_TYPES = {
    "Material", "Property", "Application",
    "Method", "Element", "Formula"
}

VALID_RELATION_TYPES = {
    "HAS_PROPERTY", "USED_IN", "HAS_ELEMENT",
    "HAS_FORMULA", "SYNTHESIZED_BY"
}

# Geçerli ilişki kombinasyonları: (source_type, relation, target_type)
LEGAL_RELATIONS = {
    ("Material",  "HAS_PROPERTY",   "Property"),
    ("Material",  "USED_IN",        "Application"),
    ("Material",  "HAS_ELEMENT",    "Element"),
    ("Material",  "HAS_FORMULA",    "Formula"),
    ("Material",  "SYNTHESIZED_BY", "Method"),
    ("Property",  "USED_IN",        "Application"),
    ("Formula",   "HAS_ELEMENT",    "Element"),
}

# Periyodik tablo sembolleri
PERIODIC_SYMBOLS = {
    "H","He","Li","Be","B","C","N","O","F","Ne",
    "Na","Mg","Al","Si","P","S","Cl","Ar","K","Ca",
    "Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn",
    "Ga","Ge","As","Se","Br","Kr","Rb","Sr","Y","Zr",
    "Nb","Mo","Tc","Ru","Rh","Pd","Ag","Cd","In","Sn",
    "Sb","Te","I","Xe","Cs","Ba","La","Ce","Pr","Nd",
    "Pm","Sm","Eu","Gd","Tb","Dy","Ho","Er","Tm","Yb",
    "Lu","Hf","Ta","W","Re","Os","Ir","Pt","Au","Hg",
    "Tl","Pb","Bi","Po","At","Rn","Fr","Ra","Ac","Th",
    "Pa","U","Np","Pu","Am","Cm","Bk","Cf","Es","Fm",
    "Md","No","Lr","Rf","Db","Sg","Bh","Hs","Mt","Ds",
    "Rg","Cn","Nh","Fl","Mc","Lv","Ts","Og","Mg","Fe"
}

# Sinonim sözlüğü — normalizasyon için
SYNONYMS = {
    "aluminum": "Al",
    "silicon":  "Si",
    "copper":   "Cu",
    "gold":     "Au",
    "silver":   "Ag",
    "iron":     "Fe",
    "carbon":   "C",
    "nitrogen": "N",
    "oxygen":   "O",
    "chemical vapor deposition": "CVD",
    "physical vapor deposition": "PVD",
    "molecular beam epitaxy":    "MBE",
    "atomic layer deposition":   "ALD",
    "gnn": "Graph Neural Network",
    "ml":  "Machine Learning",
    "ai":  "Artificial Intelligence",
}

# ─── Sonuç sınıfları ─────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class ValidatedEntity:
    name: str
    type: str
    confidence: float
    canonical_name: str  # normalize edilmiş isim

@dataclass
class ValidatedRelation:
    source: str
    target: str
    relation_type: str
    evidence: str
    confidence: float

@dataclass
class CriticalLayerResult:
    passed: bool
    entities: List[ValidatedEntity] = field(default_factory=list)
    relations: List[ValidatedRelation] = field(default_factory=list)
    rejected_entities: List[str] = field(default_factory=list)
    rejected_relations: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

# ─── Adım 1: Schema Validation ───────────────────────────────────────────────

def validate_schema(entities, relations) -> ValidationResult:
    """JSON yapısı ve tipler doğru mu?"""
    errors = []
    warnings = []

    for i, e in enumerate(entities):
        if not e.name or not e.name.strip():
            errors.append(f"Entity #{i}: boş isim")
        if e.type not in VALID_ENTITY_TYPES:
            errors.append(f"Entity '{e.name}': geçersiz tip '{e.type}'")
        if not (0.0 <= e.confidence <= 1.0):
            warnings.append(f"Entity '{e.name}': confidence aralık dışı {e.confidence}")

    for i, r in enumerate(relations):
        if not r.source or not r.target:
            errors.append(f"Relation #{i}: boş source veya target")
        if r.relation_type not in VALID_RELATION_TYPES:
            errors.append(f"Relation '{r.source}->{r.target}': geçersiz tip '{r.relation_type}'")
        if not r.evidence:
            warnings.append(f"Relation '{r.source}->{r.target}': kanıt yok")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

# ─── Adım 2: Normalizasyon ───────────────────────────────────────────────────

def normalize_name(name: str, entity_type: str) -> str:
    """İsmi normalize et: sinonim, büyük/küçük harf."""
    name = name.strip()
    lower = name.lower()

    # Sinonim kontrolü
    if lower in SYNONYMS:
        return SYNONYMS[lower]

    # Element ise capitalize
    if entity_type == "Element":
        # "al" → "Al", "si" → "Si"
        if len(name) <= 2:
            return name.capitalize()

    return name

# ─── Adım 3: Element Validation ──────────────────────────────────────────────

def validate_element(name: str) -> bool:
    """Element tipi için periyodik tablo kontrolü."""
    return name in PERIODIC_SYMBOLS or name.capitalize() in PERIODIC_SYMBOLS

# ─── Adım 4: Relation Legality ───────────────────────────────────────────────

def check_relation_legality(source_type: str, relation_type: str, target_type: str) -> bool:
    """Bu relation kombinasyonu geçerli mi?"""
    return (source_type, relation_type, target_type) in LEGAL_RELATIONS

# ─── ANA FONKSİYON ───────────────────────────────────────────────────────────

def run_critical_layer(extraction_result) -> CriticalLayerResult:
    """
    Extraction sonucunu 4 aşamada doğrula.
    LLM YOK — tamamen deterministik kod.
    """
    result = CriticalLayerResult(passed=False)

    # Adım 1: Schema validation
    schema_check = validate_schema(
        extraction_result.entities,
        extraction_result.relations
    )
    if not schema_check.valid:
        result.errors = schema_check.errors
        return result

    # Adım 2 & 3: Entity normalizasyonu + element kontrolü
    entity_map = {}  # name → ValidatedEntity (lookup için)

    for e in extraction_result.entities:
        canonical = normalize_name(e.name, e.type)

        # Element tipi ise periyodik tablo kontrolü
        if e.type == "Element":
            if not validate_element(canonical):
                result.rejected_entities.append(
                    f"'{e.name}' geçerli element sembolü değil"
                )
                continue

        # Güven eşiği
        if e.confidence < 0.5:
            result.rejected_entities.append(
                f"'{e.name}' düşük güven skoru: {e.confidence}"
            )
            continue

        validated = ValidatedEntity(
            name=e.name,
            type=e.type,
            confidence=e.confidence,
            canonical_name=canonical
        )
        entity_map[e.name] = validated
        result.entities.append(validated)

    # Adım 4: Relation legality kontrolü
    for r in extraction_result.relations:
        source_entity = entity_map.get(r.source)
        target_entity = entity_map.get(r.target)

        # Source veya target entity geçerlileştirilmemiş mi?
        if not source_entity:
            result.rejected_relations.append(
                f"'{r.source}->{r.target}': source entity bulunamadı"
            )
            continue
        if not target_entity:
            result.rejected_relations.append(
                f"'{r.source}->{r.target}': target entity bulunamadı"
            )
            continue

        # Relation tipi geçerli mi?
        if not check_relation_legality(
            source_entity.type, r.relation_type, target_entity.type
        ):
            result.rejected_relations.append(
                f"'{r.source}({source_entity.type})-[{r.relation_type}]->"
                f"{r.target}({target_entity.type})': geçersiz kombinasyon"
            )
            continue

        # Güven eşiği
        if r.confidence < 0.5:
            result.rejected_relations.append(
                f"'{r.source}->{r.target}': düşük güven {r.confidence}"
            )
            continue

        result.relations.append(ValidatedRelation(
            source=source_entity.canonical_name,
            target=target_entity.canonical_name,
            relation_type=r.relation_type,
            evidence=r.evidence,
            confidence=r.confidence
        ))

    result.passed = len(result.entities) > 0
    return result


# ─── TEST ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Mock extraction result
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    from agents.extraction_agent import Entity, Relation, ExtractionResult

    mock = ExtractionResult(
        paper_title="Test Paper",
        entities=[
            Entity("Nanowire",         "Material",    0.9),
            Entity("Superconductivity","Property",    0.9),
            Entity("Quantum Computing","Application", 0.9),
            Entity("CVD",              "Method",      0.9),
            Entity("Al",               "Element",     0.9),
            Entity("Si",               "Element",     0.9),
            Entity("Al-Si",            "Formula",     0.9),
            Entity("Unobtanium",       "Element",     0.9),  # geçersiz element
            Entity("FakeRelation",     "Material",    0.3),  # düşük güven
        ],
        relations=[
            Relation("Nanowire","Superconductivity","HAS_PROPERTY","...exhibits superconductivity...",0.9),
            Relation("Nanowire","Quantum Computing","USED_IN","...quantum computing applications...",0.9),
            Relation("Nanowire","CVD","SYNTHESIZED_BY","...synthesized using CVD...",0.9),
            Relation("Nanowire","Al","HAS_ELEMENT","...aluminum...",0.9),
            Relation("Nanowire","Al-Si","HAS_FORMULA","...Al-Si nanowires...",0.9),
            Relation("Nanowire","Quantum Computing","HAS_ELEMENT","INVALID COMBO",0.9),  # geçersiz!
        ]
    )

    result = run_critical_layer(mock)

    print("=" * 55)
    print("CRITICAL LAYER SONUCU")
    print("=" * 55)
    print(f"Geçti mi: {'✅ EVET' if result.passed else '❌ HAYIR'}")

    print(f"\n✅ Kabul edilen entity'ler ({len(result.entities)}):")
    for e in result.entities:
        print(f"   [{e.type:12}] {e.name} → '{e.canonical_name}'")

    print(f"\n❌ Reddedilen entity'ler ({len(result.rejected_entities)}):")
    for r in result.rejected_entities:
        print(f"   {r}")

    print(f"\n✅ Kabul edilen relation'lar ({len(result.relations)}):")
    for r in result.relations:
        print(f"   {r.source} --[{r.relation_type}]--> {r.target}")

    print(f"\n❌ Reddedilen relation'lar ({len(result.rejected_relations)}):")
    for r in result.rejected_relations:
        print(f"   {r}")