import scrapy

class PokemonsSpider(scrapy.Spider):
    name = "pokedex"
    start_urls = ["https://pokemondb.net/pokedex/all"]

    def parse(self, response):
        pokemons_html = response.css('.cell-name')
        for html in pokemons_html:
            pokemon_url = html.css('a').attrib['href']
            yield response.follow(pokemon_url, callback=self.parsePokemonPage)

    def parsePokemonPage(self,response):
        altura_raw = response.css('table.vitals-table tr:contains("Height") td::text').get()
        peso_raw = response.css('table.vitals-table tr:contains("Weight") td::text').get()
        altura = float(altura_raw.split("m")[0].strip())*100 if altura_raw and "m" in altura_raw else None
        peso = float(peso_raw.split("kg")[0].strip()) if peso_raw and "kg" in peso_raw else None
        
        evolucoes = []
        for evolucao in response.css('div.infocard-list-evo div.infocard'):
            nameEvo = evolucao.css('a.ent-name::text').get()
            numero = evolucao.css('small::text').get()

            # NOVA EXTRAÇÃO PARA ITENS E LEVEL
            condicao_evolucao_span = evolucao.xpath('./following-sibling::span[1]')
            item = None
            level = None

            if condicao_evolucao_span:
                item_element = condicao_evolucao_span.css('small a.itype')
                if item_element:
                    item = item_element.css('::text').get()
                
                condicao_texto = condicao_evolucao_span.css('small::text').get()
                if condicao_texto and 'Level' in condicao_texto:
                    level = condicao_texto.split('Level ')[1].replace(')', '').strip()

            urlEvo = response.urljoin(evolucao.css('a::attr(href)').get())

            if nameEvo:
                evolucoes.append({
                    "nome": nameEvo,
                    "numero": numero,
                    "url": urlEvo,
                    "level": level,
                    "item": item 
                })

        habilidades = []
        for habilidade in response.css('table.vitals-table tr:contains("Abilities") a'):
            habilidades.append({
                "nome": habilidade.css('::text').get(),
                "url": response.urljoin(habilidade.css('::attr(href)').get()),
                "descricao": habilidade.attrib.get('title')
            })

        # Lista fixa com todos os tipos existentes
        efetividade = {}
        
        def processar_valor_efetividade(valor_raw):
            if not valor_raw:
                return 1.0
            
            valor_limpo = valor_raw.strip().replace('×', '').replace('x', '')
            
            try:
                if valor_limpo == '½' or valor_limpo == '1⁄2':
                    return 0.5
                elif valor_limpo == '¼' or valor_limpo == '1⁄4':
                    return 0.25
                elif valor_limpo == '2':
                    return 2.0
                elif valor_limpo == '4':
                    return 4.0
                elif valor_limpo == '0':
                    return 0.0
                elif valor_limpo == '1' or valor_limpo == '':
                    return 1.0
                else:
                    return float(valor_limpo) if valor_limpo else 1.0
            except (ValueError, TypeError):
                return 1.0
        
        # Procura pela tabela de efetividade (considerando múltiplas linhas)
        tabela_defesa = response.css('table.type-table')
        
        if tabela_defesa:
            # Pega TODOS os tipos de TODAS as linhas de cabeçalho
            todos_tipos = []
            todas_linhas_valores = []
            
            # Processa cada linha da tabela
            linhas = tabela_defesa.css('tr')
            
            for linha in linhas:
                # Se tem cabeçalho (th), coleta os tipos
                tipos_linha = linha.css('th .type-icon::text, th .type-abbr::text').getall()
                if tipos_linha:
                    todos_tipos.extend(tipos_linha)
                
                # Se tem células de valor (td), coleta os valores
                valores_linha = linha.css('td')
                if valores_linha:
                    todas_linhas_valores.extend(valores_linha)
            
            # Mapeia tipos para valores usando posição
            for i, tipo in enumerate(todos_tipos):
                if i < len(todas_linhas_valores):
                    valor_raw = todas_linhas_valores[i].css('::text').get()
                    efetividade[tipo] = processar_valor_efetividade(valor_raw)
                else:
                    efetividade[tipo] = 1.0
        
        if not efetividade:
            for tabela in response.css('table.type-table'):
                linhas_cabecalho = tabela.css('tr:has(th)')
                linhas_valores = tabela.css('tr:has(td)')
                
                tipos_por_linha = []
                valores_por_linha = []
                
                # Coleta tipos de cada linha de cabeçalho
                for linha in linhas_cabecalho:
                    tipos = linha.css('th .type-icon::text, th .type-abbr::text').getall()
                    tipos_por_linha.append(tipos)
                
                # Coleta valores de cada linha de dados
                for linha in linhas_valores:
                    valores = linha.css('td')
                    valores_por_linha.append(valores)
                
                # Mapeia considerando que cada linha de tipos corresponde a uma linha de valores
                indice_valor_global = 0
                for linha_tipos in tipos_por_linha:
                    for tipo in linha_tipos:
                        valor_encontrado = False
                        for linha_valores in valores_por_linha:
                            if indice_valor_global < len(linha_valores):
                                valor_raw = linha_valores[indice_valor_global].css('::text').get()
                                efetividade[tipo] = processar_valor_efetividade(valor_raw)
                                valor_encontrado = True
                                break
                            indice_valor_global -= len(linha_valores)
                        
                        if not valor_encontrado:
                            efetividade[tipo] = 1.0
                        
                        indice_valor_global += 1
                
                if efetividade:
                    break

        yield{
            'name' : response.css('#main h1::text').get(),
            'id' : response.css('table.vitals-table tr:contains("National №") strong::text').get(),
            'url' : response.url,
            "evolucoes": evolucoes,
            "tamanho" : altura,
            "peso" : peso,
            "tipo" : response.css('table.vitals-table tr:contains("Type") a::text').getall(),
            "habilidades" : habilidades,
            "efetividade": efetividade
        }
        pass