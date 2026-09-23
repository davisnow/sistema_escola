def calcular_media_etapa(trab: float, vp: float, vg: float, rec: float = None) -> float:
    media = (trab + vp + vg) / 3.0
    
    if rec is not None and rec > media:
        media = rec
        
    media_arredondada = round(media, 2)
    if 5.75 <= media_arredondada < 6.0:
        return 6.0
        
    return round(media, 1)

def verificar_resultado_final(medias_etapas: list, rec_final: float = None) -> str:
    if len(medias_etapas) < 4:
        return "EM ANDAMENTO"
    
    media_anual = sum(medias_etapas) / 4.0
    if 5.75 <= round(media_anual, 2) < 6.0:
        media_anual = 6.0
        
    if media_anual >= 5.75:
        return "APROVADO"
        
    if rec_final is not None and rec_final >= 5.75:
        return "APROVADO"
        
    return "REPROVADO"