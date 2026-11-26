"""Local, deterministic administrative assistant; no external data transfer."""
import unicodedata

def answer(question, docs, company_count):
    q=''.join(c for c in unicodedata.normalize('NFKD',question.lower()) if not unicodedata.combining(c))
    expired=[d for d in docs if d['status']=='expired']; soon=[d for d in docs if d['status']=='soon']
    if any(k in q for k in ('relance','priorit','urgence','attention')): rows=expired+soon; title='Actions prioritaires'
    elif any(k in q for k in ('expire','expiration')): rows=expired; title='Documents expirés'
    elif any(k in q for k in ('semaine','7 jours','7 jour')): rows=[d for d in soon if d['days']<=7]; title='Échéances dans les 7 jours'
    elif any(k in q for k in ('echeance','renouvel','30 jours')): rows=soon; title='Échéances dans les 30 jours'
    elif any(k in q for k in ('bilan','resume','situation','statistique','rapport')):
        return {'title':'Synthèse administrative','message':f'{company_count} entreprises, {len(docs)} documents suivis, {len(expired)} expirés et {len(soon)} à renouveler dans les 30 jours.','items':(expired+soon)[:30],'total':len(expired)+len(soon)}
    else: return {'title':'Question non prise en charge','message':'Je peux résumer votre situation, lister les échéances à 7 ou 30 jours, les documents expirés et les relances à préparer.','items':[],'total':0}
    return {'title':title,'message':f'{len(rows)} document(s) concerné(s). Vérifiez les informations sur les originaux.','items':rows[:30],'total':len(rows)}
