"""Listas de palavras do filtro de notícias.

Termo com `*` vale como prefixo ("acident*"); sem `*`, só a palavra inteira.
Texto sem acento e em minúsculas. Alterar aqui não exige mexer no script.
"""

NEGATIVAS = """
mort* morr* matou matam matar assassin* homicid* feminicid* suicid* luto vitima* ferid*
crime* crimin* roub* furt* estupr* sequestr* tortur* abuso* fraude* corrupc* escandalo*
acusad* condenad* condenac* preso* prisao denunc*
violenc* violent* agress* ataque* atentado* terror* bomba* bombardeio* tiroteio massacre*
genocid* guerra* conflito* invas* ameac* refugiad*
tragedia* acidente* desastre* incendio* explos* naufrag* terremoto* enchente* inundac*
deslizamento* colapso
crise* falenc* desemprego inflac* recessao epidemia* pandemia* surto* fome miseria
emagrec* dieta* ozempic wegovy mounjaro tirzepatida semaglutida jejum detox
anorexi* bulimi* bariatric* lipoaspirac* lipo rinoplastia* plastica plasticas
botox preenchimento* harmonizacao silicone estetic*
droga* cetamina cocaina heroina overdose entorpecente* detent* presidiari* penitenciaria*
execucao execucoes executad* trauma* incontinencia
""".split()

# Negativas condicionais: o gatilho só barra se nenhum termo "libera" aparecer.
# Ex.: "doença" sem cura é negativa; "doença" com cura passa.
CONDICIONAIS = [
    (
        ["doenc*", "enfermidade*"],
        ["cura", "curas", "curou", "curam", "curar", "curado", "curada", "vacina*"],
    ),
]

EXCECOES_NEGATIVAS = {"mortadela", "morro", "morros"}

POLITICAS = """
governo* governador* prefeit* president* ministr* ministerio* congresso senado* senador*
deputad* camara parlament* legisla* planalto stf stj tse
eleica* eleito* eleitor* voto* votac* urna* candidat* partido* politic* diplomat*
ditadura* democracia* golpe* impeachment
lula bolsonaro trump biden putin zelensky maduro milei netanyahu vorcaro
""".split()
