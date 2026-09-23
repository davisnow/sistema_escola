import sqlite3

DB_NAME = "escola.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alunos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        turma TEXT NOT NULL,
        turno TEXT DEFAULT 'MANHÃ',
        ativo INTEGER DEFAULT 1
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS avaliacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id INTEGER NOT NULL,
        disciplina TEXT NOT NULL,
        etapa INTEGER NOT NULL,
        trabalho REAL DEFAULT 0.0,
        vp REAL DEFAULT 0.0,
        vg REAL DEFAULT 0.0,
        recuperacao REAL,
        faltas INTEGER DEFAULT 0,
        FOREIGN KEY (aluno_id) REFERENCES alunos(id),
        UNIQUE(aluno_id, disciplina, etapa)
    )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()