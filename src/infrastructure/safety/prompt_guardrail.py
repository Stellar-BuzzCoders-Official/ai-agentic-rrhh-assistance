import re
import logging
from typing import Tuple
from src.application.ports.outbound import ContentSafetyPort

logger = logging.getLogger(__name__)

# Expresiones regulares para detección de prompt injection y jailbreaks
PROMPT_INJECTION_PATTERNS = [
    r"(?i)\b(ignora|olvida|deshaz|omite)\b.*\b(instrucciones|reglas|directivas|prompt|comandos)\b",
    r"(?i)\b(ignore|forget|disregard|override)\b.*\b(instructions|rules|system prompt|directives)\b",
    r"(?i)\b(actúa|actua|comportate|finge)\s+(como|ser)\b.*\b(sin\s+restricciones|dan|desarrollador|hacker|root|admin)\b",
    r"(?i)\b(act\s+as|pretend\s+to\s+be)\b.*\b(unrestricted|dan|jailbreak|developer\s+mode|no\s+rules)\b",
    r"(?i)\b(muestra|muéstrame|muestrame|dame|revela|imprime|repite|dime)\b.*\b(system\s+prompt|prompt(\s+del\s+sistema)?|instrucciones\s+del\s+sistema|instrucciones\s+ocultas|reglas\s+secretas)\b",
    r"(?i)\b(show|reveal|display|repeat|leak|tell\s+me)\b.*\b(system\s+prompt|hidden\s+instructions|secret\s+rules)\b",
    r"(?i)\b(jailbreak|dan\s+mode|dan\b|developer\s+mode|bypass\s+security|desactivar\s+seguridad|desactiva\s+tus\s+reglas|desactiva\s+los\s+filtros)\b",
    r"(?i)\byou\s+are\s+no\s+longer\b",
    r"(?i)\bahora\s+ya\s+no\s+eres\b",
]

# Expresiones regulares para detección de solicitudes de generación de código arbitrario
# (El asistente es de screening de RRHH, no un generador de código o IDE)
CODE_GENERATION_PATTERNS = [
    r"(?i)\b(escribe|escríbeme|escribeme|genera|generame|genérame|crea|creame|créame|dame|haz|hazme|programa|codifica|construye)\b.*\b(un\s+|una\s+|el\s+|la\s+)?(código|codigo|script|programa|algoritmo|función|funcion|snippet|solución\s+en\s+código)\b",
    r"(?i)\b(write|generate|create|give\s+me|code|build)\b.*\b(a\s+|an\s+|the\s+)?(code|script|program|algorithm|function|snippet|solution\s+in\s+code)\b",
    r"(?i)\b(cómo|como)\s+(programar|codificar|escribir\s+código|hacer\s+un\s+script)\b",
    r"(?i)\b(how\s+to)\s+(code|program|write\s+a\s+script|create\s+code)\b",
    r"(?i)\b(resuelve|soluciona)\b.*\b(ejercicio\s+de\s+código|leetcode|hackerrank|algoritmo)\b",
    r"(?i)\b(desarrolla|crea|escribe)\b.*\b(malware|keylogger|exploit|virus|troyano|backdoor|payload)\b",
    r"(?i)\b(inyección\s+sql|sql\s+injection|xss\s+payload|reverse\s+shell)\b",
]

# Excepciones válidas de screening de RRHH (no deben bloquearse)
ALLOWED_RECRUITMENT_MARKERS = [
    r"(?i)\b(requisito|perfil|puesto|vacante|candidato|evalua|evaluación|screening|skills|competencias|experiencia)\b",
    r"(?i)\b(cv|curriculum|hoja\s+de\s+vida|file_id)\b",
]


class PromptInjectionGuardrail(ContentSafetyPort):
    """
    Guardrail de seguridad especializado en:
    1. Neutralización de ataques de Prompt Injection y Jailbreaks.
    2. Bloqueo de peticiones fuera de dominio (ej. solicitudes de generación de código arbitrario).
    3. Prevención de exfiltración de prompts del sistema.
    """

    async def check_input(self, text: str) -> Tuple[bool, str]:
        if not text or not text.strip():
            return True, ""

        clean_text = text.strip()

        # 1. Verificar si es un ataque de prompt injection / jailbreak
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, clean_text):
                logger.warning("Intento de Prompt Injection detectado por patrón: %s", pattern)
                return False, (
                    "Intento de manipulación de instrucciones (Prompt Injection / Jailbreak) detectado. "
                    "Este sistema opera bajo directivas estrictas de seguridad de Recursos Humanos."
                )

        # 2. Verificar solicitudes de generación de código arbitrario
        for pattern in CODE_GENERATION_PATTERNS:
            if re.search(pattern, clean_text):
                # Validar que no sea una definición legítima de perfil de puesto (ej: "Buscamos un perfil que escriba código limpio")
                if not any(re.search(rec_marker, clean_text) for rec_marker in ALLOWED_RECRUITMENT_MARKERS):
                    logger.warning("Solicitud de generación de código detectada: %s", pattern)
                    return False, (
                        "Este asistente está especializado exclusivamente en selección de talento y evaluación técnica de CVs. "
                        "No está autorizado para generar código fuente, programar scripts ni resolver ejercicios de programación arbitrarios."
                    )

        return True, ""
