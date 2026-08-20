import re

class CoordinateParser:
    """
    Parser robusto de coordenadas geográficas.
    Trata números decimais, strings com vírgula, formatos GMS (Graus-Minutos-Segundos)
    com hífens como '-19-57-19,08' ou símbolos como '19°57'19.08" S'.
    """

    @staticmethod
    def parse_coordinate(val, is_latitude=True):
        """
        Converte qualquer formato de coordenada para float decimal.
        Retorna float ou None se for inválido.
        """
        if val is None:
            return None
        
        # Se já for número
        if isinstance(val, (int, float)):
            if str(val).lower() == 'nan':
                return None
            num = float(val)
            return num if CoordinateParser.is_valid(num, is_latitude) else None

        s = str(val).strip()
        if not s or s.lower() == 'nan' or s.lower() == 'null':
            return None

        # 1. Testar conversão direta com substituição de vírgula por ponto (ex: "-20,170578")
        try:
            cleaned = s.replace(',', '.').replace(' ', '')
            num = float(cleaned)
            return num if CoordinateParser.is_valid(num, is_latitude) else None
        except ValueError:
            pass

        # 2. Formato com hífens (ex: "-19-57-19,08" ou "19-57-19.08-S")
        # Padrão: [+-]?(\d+)[\-\s](\d+)[\-\s](\d+(?:[.,]\d+)?)
        hyphen_pattern = re.compile(
            r'^([+\-])?\s*(\d{1,3})[\-\s]+(\d{1,2})[\-\s]+(\d{1,2}(?:[.,]\d+)?)\s*([NSEOWnseow])?$'
        )
        m = hyphen_pattern.match(s)
        if m:
            sign_str, deg_str, min_str, sec_str, direction = m.groups()
            deg = float(deg_str)
            min_ = float(min_str)
            sec = float(sec_str.replace(',', '.'))
            
            decimal = deg + (min_ / 60.0) + (sec / 3600.0)
            
            # Trata sinal
            is_negative = False
            if sign_str == '-':
                is_negative = True
            elif direction and direction.upper() in ['S', 'W', 'O']:
                is_negative = True
            elif not sign_str and not direction:
                # No Brasil coordenadas de latitude e longitude são quase sempre negativas
                is_negative = True
                
            if is_negative:
                decimal = -abs(decimal)
                
            return decimal if CoordinateParser.is_valid(decimal, is_latitude) else None

        # 3. Formato com símbolos GMS: 19°57'19.08"S ou -19° 57' 19.08"
        gms_pattern = re.compile(
            r'^([+\-])?\s*(\d{1,3})[°º\s]+(\d{1,2})[\'’\s]+(\d{1,2}(?:[.,]\d+)?)[″"\s]*([NSEOWnseow])?$'
        )
        m2 = gms_pattern.match(s)
        if m2:
            sign_str, deg_str, min_str, sec_str, direction = m2.groups()
            deg = float(deg_str)
            min_ = float(min_str)
            sec = float(sec_str.replace(',', '.'))
            
            decimal = deg + (min_ / 60.0) + (sec / 3600.0)
            
            is_negative = False
            if sign_str == '-':
                is_negative = True
            elif direction and direction.upper() in ['S', 'W', 'O']:
                is_negative = True
            elif not sign_str and not direction:
                is_negative = True
                
            if is_negative:
                decimal = -abs(decimal)
                
            return decimal if CoordinateParser.is_valid(decimal, is_latitude) else None

        return None

    @staticmethod
    def is_valid(coord, is_latitude=True):
        """Verifica se a coordenada está dentro dos limites geográficos terrestres válidos."""
        if coord is None:
            return False
        if is_latitude:
            return -90.0 <= coord <= 90.0
        else:
            return -180.0 <= coord <= 180.0
