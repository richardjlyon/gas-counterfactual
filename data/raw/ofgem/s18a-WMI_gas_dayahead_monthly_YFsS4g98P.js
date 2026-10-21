(function () {
  //Inject code v5.2

  var highcharts = document.createElement('script');
  var injectVersion = 6;
  var cdn = 'https://app.everviz.com/resources/highcharts/11.4.8/';
  var loaded = 0;  
  var encodedUrl = encodeURI('https://https://app.everviz.com//show/YFsS4g98P');
  var chartCreated = false;
  var delayGen = 0;
  var scripts = [
    "highcharts.js",
    "modules/stock.js",
    "highcharts-more.js",
    "highcharts-3d.js",
    "modules/data.js",
    "modules/exporting.js",
    "modules/funnel.js",
    "modules/solid-gauge.js",
    "modules/export-data.js",
    "modules/accessibility.js"
  ];

  const inEmbedCode = window.location.pathname.indexOf('/embed/') > -1;
  const inEverviz = window.location.origin === 'https://app.everviz.com';
  const loadHighchartsModules = inEverviz && !inEmbedCode;

  var legacyElementClassName = 'highcharts-YFsS4g98P';
  var elementClassName = 'everviz-YFsS4g98P';
  var externalCSS = [
    "https://app.everviz.com/resources/css/highcharts-data-table.css"
  ];

  var extraScripts = [
  "https://app.everviz.com/resources/js/highcharts-scroll-animation.js",
  "https://app.everviz.com/resources/js/everviz-utils.js",
  "https://app.everviz.com/resources/js/highcharts-overrides.js",
  "https://app.everviz.com/resources/js/highcharts-resize.js",
  "https://app.everviz.com/resources/js/highcharts-parse-data.js",
  ];

  var options = {"chart":{"type":"line","polar":false},"rangeSelector":{"enabled":false},"title":{"align":"left","x":10,"useHTML":true,"style":{"fontFamily":"Default","color":"#333333","fontSize":"18px","fontWeight":"normal","fontStyle":"normal"},"text":"Gas Prices: Day Ahead Contracts - Monthly Average (Great Britain)"},"subtitle":{"align":"left","x":10,"useHTML":true,"text":"\n"},"plotOptions":{"series":{"allowPointSelect":true,"states":{"select":{"color":"#EFFFEF","borderColor":"black","dashStyle":"dot"}},"label":{"enabled":false},"marker":{"enabled":false},"lineWidth":3,"dataLabels":{"enabled":false}}},"credits":{"href":"https://www.ofgem.gov.uk","position":{"x":-12,"y":-35},"style":{"fontSize":"14px","color":"#666666"},"text":"Ofgem analysis of broker data","enabled":true},"lang":{"shortMonths":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],"weekdays":["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"],"months":["January","February","March","April","May","June","July","August","September","October","November","December"],"numericSymbols":["k","M","G","T","P","E"]},"colors":["#e86e1e","#45286f","#e2c700","#cd1f45","#2363af","#51c1b5","#a1abb2","#9e712a","#0a4125","#a0b100","#000000","#9e712a","#51c1b5"],"legend":{"align":"center","verticalAlign":"bottom","itemMarginBottom":10,"x":0,"symbolRadius":2,"enabled":true,"layout":"horizontal"},"series":[{"turboThreshold":0,"type":"line","name":"Price","data":[],"_colorIndex":0,"_symbolIndex":0}],"stockTools":{"gui":{"enabled":false}},"navigation":{"bindingsClassName":"tools-container","events":{}},"responsive":{"rules":[]},"caption":{"x":9,"y":1,"style":{"fontFamily":"Default","color":"#666666","fontSize":"14px","fontWeight":"normal","fontStyle":"normal","fill":"#666666","width":"1184px"},"text":"<div>Information correct as of August 2026</div>","useHTML":true},"exporting":{"url":"https://api.everviz.com/export","sourceHeight":null,"sourceWidth":null},"labels":{"items":[]},"xAxis":{"minPadding":0,"maxPadding":0,"overscroll":0,"ordinal":true,"labels":{"overflow":"justify","format":"{value:%b-%Y}"},"showLastLabel":true,"type":"datetime","categories":null,"startOnTick":false,"endOnTick":false,"index":0,"isX":true,"title":{"text":"\n","useHTML":true}},"yAxis":{"labels":{"y":-2},"opposite":false,"showLastLabel":false,"title":{"text":"p/therm (GBp)\n","useHTML":true},"index":0},"annotations":[],"navigator":{"xAxis":{"labels":{"format":"{value:%b-%Y}"}},"enabled":true},"pane":{"background":[]},"tooltip":{},"data":{"csv":"\"Category\",\"Price\"\n\"10/01/2009\",25.18\n\"11/01/2009\",26.99\n\"12/01/2009\",31.42\n\"01/01/2010\",39.77\n\"02/01/2010\",35.78\n\"03/01/2010\",32.14\n\"04/01/2010\",32.79\n\"05/01/2010\",39.49\n\"06/01/2010\",42.15\n\"07/01/2010\",45.94\n\"08/01/2010\",42.61\n\"09/01/2010\",40.77\n\"10/01/2010\",46\n\"11/01/2010\",49.66\n\"12/01/2010\",62.26\n\"01/01/2011\",55.98\n\"02/01/2011\",53.74\n\"03/01/2011\",60.39\n\"04/01/2011\",57.23\n\"05/01/2011\",57.01\n\"06/01/2011\",58.25\n\"07/01/2011\",55.09\n\"08/01/2011\",54.06\n\"09/01/2011\",53.64\n\"10/01/2011\",56.05\n\"11/01/2011\",58.15\n\"12/01/2011\",56.04\n\"01/01/2012\",54.43\n\"02/01/2012\",65.41\n\"03/01/2012\",58.44\n\"04/01/2012\",59.94\n\"05/01/2012\",57.01\n\"06/01/2012\",55.15\n\"07/01/2012\",55.6\n\"08/01/2012\",54.53\n\"09/01/2012\",60.45\n\"10/01/2012\",64.35\n\"11/01/2012\",65.63\n\"12/01/2012\",65.5\n\"01/01/2013\",66.83\n\"02/01/2013\",68.88\n\"03/01/2013\",86.57\n\"04/01/2013\",69.98\n\"05/01/2013\",66.14\n\"06/01/2013\",60.47\n\"07/01/2013\",65.23\n\"08/01/2013\",64.65\n\"09/01/2013\",65.71\n\"10/01/2013\",65.08\n\"11/01/2013\",68.29\n\"12/01/2013\",69.35\n\"01/01/2014\",65.1\n\"02/01/2014\",58.86\n\"03/01/2014\",56.53\n\"04/01/2014\",49.89\n\"05/01/2014\",45.33\n\"06/01/2014\",39.5\n\"07/01/2014\",37.51\n\"08/01/2014\",40.61\n\"09/01/2014\",48.43\n\"10/01/2014\",50.42\n\"11/01/2014\",54.84\n\"12/01/2014\",53.62\n\"01/01/2015\",46.1\n\"02/01/2015\",50.47\n\"03/01/2015\",47.23\n\"04/01/2015\",46.86\n\"05/01/2015\",44.09\n\"06/01/2015\",43.37\n\"07/01/2015\",43.47\n\"08/01/2015\",39.69\n\"09/01/2015\",41.04\n\"10/01/2015\",39.56\n\"11/01/2015\",35.9\n\"12/01/2015\",34.03\n\"01/01/2016\",32.05\n\"02/01/2016\",29.66\n\"03/01/2016\",29.6\n\"04/01/2016\",29.44\n\"05/01/2016\",30.41\n\"06/01/2016\",34.2\n\"07/01/2016\",34.3\n\"08/01/2016\",30.36\n\"09/01/2016\",28.36\n\"10/01/2016\",42.83\n\"11/01/2016\",48.12\n\"12/01/2016\",46.53\n\"01/01/2017\",53.39\n\"02/01/2017\",51.01\n\"03/01/2017\",41.02\n\"04/01/2017\",39.73\n\"05/01/2017\",39.29\n\"06/01/2017\",34.84\n\"07/01/2017\",36.21\n\"08/01/2017\",42.57\n\"09/01/2017\",46\n\"10/01/2017\",45.4\n\"11/01/2017\",52.95\n\"12/01/2017\",58.29\n\"01/01/2018\",50.44\n\"02/01/2018\",58.96\n\"03/01/2018\",64.3\n\"04/01/2018\",50.94\n\"05/01/2018\",55.58\n\"06/01/2018\",54.97\n\"07/01/2018\",57.93\n\"08/01/2018\",62.83\n\"09/01/2018\",73.72\n\"10/01/2018\",66.53\n\"11/01/2018\",64.37\n\"12/01/2018\",63.74\n\"01/01/2019\",57.71\n\"02/01/2019\",47.09\n\"03/01/2019\",39.31\n\"04/01/2019\",34.98\n\"05/01/2019\",31.43\n\"06/01/2019\",27.96\n\"07/01/2019\",29.6\n\"08/01/2019\",27.75\n\"09/01/2019\",24.87\n\"10/01/2019\",25.65\n\"11/01/2019\",38.04\n\"12/01/2019\",32.14\n\"01/01/2020\",27.9\n\"02/01/2020\",23.5\n\"03/01/2020\",22.92\n\"04/01/2020\",13.75\n\"05/01/2020\",11.59\n\"06/01/2020\",13.18\n\"07/01/2020\",13.24\n\"08/01/2020\",20.22\n\"09/01/2020\",29.9\n\"10/01/2020\",38.23\n\"11/01/2020\",37.57\n\"12/01/2020\",45.69\n\"01/01/2021\",59.01\n\"02/01/2021\",45.94\n\"03/01/2021\",44.96\n\"04/01/2021\",54.77\n\"05/01/2021\",65.2\n\"06/01/2021\",72.01\n\"07/01/2021\",90.88\n\"08/01/2021\",110.04\n\"09/01/2021\",162.1\n\"10/01/2021\",213.76\n\"11/01/2021\",201.13\n\"12/01/2021\",270.96\n\"01/01/2022\",203.75\n\"02/01/2022\",187.72\n\"03/01/2022\",313.57\n\"04/01/2022\",186.13\n\"05/01/2022\",105.31\n\"06/01/2022\",149.49\n\"07/01/2022\",247.71\n\"08/01/2022\",356\n\"09/01/2022\",263.44\n\"10/01/2022\",109.26\n\"11/01/2022\",138.42\n\"12/01/2022\",277.14\n\"01/01/2023\",152.45\n\"02/01/2023\",134.54\n\"03/01/2023\",107.97\n\"04/01/2023\",101.47\n\"05/01/2023\",73.53\n\"06/01/2023\",80.52\n\"07/01/2023\",71.58\n\"08/01/2023\",83.97\n\"09/01/2023\",92.21\n\"10/01/2023\",102.17\n\"11/01/2023\",105.53\n\"12/01/2023\",84.73\n\"01/01/2024\",73.83\n\"02/01/2024\",63.28\n\"03/01/2024\",68.5\n\"04/01/2024\",71.23\n\"05/01/2024\",75.96\n\"06/01/2024\",82.53\n\"07/01/2024\",94.18\n\"08/01/2024\",84.5\n\"09/01/2024\",86.58\n\"10/01/2024\",96.79\n\"11/01/2024\",111.56\n\"12/01/2024\",111.47\n\"01/01/2025\",123.02\n\"02/01/2025\",125.43\n\"03/01/2025\",102.31\n\"04/01/2025\",86.29\n\"05/01/2025\",82.54\n\"06/01/2025\",86.28\n\"07/01/2025\",81.16\n\"08/01/2025\",79.28\n\"09/01/2025\",79.35\n\"10/01/2025\",78.03\n\"11/01/2025\",76.15\n\"12/01/2025\",70.94\n\"01/01/2026\",90.4\n\"02/01/2026\",79.39\n\"03/01/2026\",132.42\n\"04/01/2026\",111.78\n\"05/01/2026\",117.89\n\"06/01/2026\",110.14","seriesMapping":[{"x":0,"y":1,"category":0,"price":1}],"itemDelimiter":",","decimalPoint":".","columnTypes":["date","float"],"dateFormat":"mm/dd/YYYY","assignDataFields":[{"labels":"A","values":"B"}]}};
  var optionsStub;
  
  var templateDataSettings = {};

  var pluginCode = {};;

  function isScriptAlreadyIncluded(src){

    var scripts = document.getElementsByTagName("script");
    for (var i = 0; i < scripts.length; i++) {
      if (scripts[i].hasAttribute('src')) {
        const scriptTag = scripts[i].getAttribute('src') || '';
        if ((scriptTag.indexOf(src) >= 0) || 
            (scriptTag.indexOf('highcharts.src.js') > -1 && src === 'highcharts.js') ||
            ((scriptTag.indexOf('stock/highstock.js') > -1) && src === 'modules/highstock.js') ||
             (loadHighchartsModules && src === 'highcharts.js')) {
          return true;
        }
      }
    }
    return false;
  }

  function loadCSS() {
    var cssLength = externalCSS.length;
    for(var i=0; i < cssLength; i++) {
      var css = document.createElement('link');
      css.rel  = 'stylesheet';
      css.type = "text/css";
      css.href = externalCSS[i];
      document.body.appendChild(css);
    }
  }

  function allScriptsIncluded(){
    var allScripts = scripts.concat(extraScripts);
    var haveAllScriptsBeenIncluded = true;
    var scriptsToUse = document.getElementsByTagName("script");
    for(var n=0;n<allScripts.length;n++) {
      if (!isScriptAlreadyIncluded(allScripts[n], scriptsToUse)) {
        haveAllScriptsBeenIncluded = false;
        break;
      }
    }
    return haveAllScriptsBeenIncluded;
  }

  function modifyOptions(){
    if (options.data && !options.data.complete) {
      options.data.complete = function(chartOptions) {
        const keys = Object.keys(templateDataSettings || {});
        keys.forEach(function(key) {
          const serie = chartOptions.series[key];
          (serie.data || []).forEach(function(d, i) {
            if (templateDataSettings[key].data && templateDataSettings[key].data[i]) {
              window["everviz"].merge(d, templateDataSettings[key].data[i]);
            }
          })
        })

        if (options && options.chart && options.chart.type === 'packedbubble') {
          chartOptions.series.forEach((series) => {
            series.data = series.data.filter((point) => point.value);
          });
        }

        return chartOptions;
      }
    }
    
    optionsStub = window["everviz"].createStub(options);
    window["everviz"].merge(options, pluginCode);
    if ('StockChart' === 'Map') window["everviz"].modifyMapType(options);
  }

  function createChart() {
    if(chartCreated) return;

    var hasProj4 = extraScripts.indexOf('https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.3.6/proj4.js') > -1;

    if (!allScriptsIncluded() || 
      (hasProj4 && !window.proj4) || 
      !window["everviz"].merge ||
      !window["everviz"].createStub) {
      setTimeout(createChart, 200);
      return;
    }  

    modifyOptions();

    if (hasProj4) delayGen = 100;

    if (typeof window['Highcharts'] !== 'undefined') {
      
    if (window['everviz'] && window['everviz'].tooltipFormatter && 
        options.everviz && options.everviz.tooltip){
      if (!options.tooltip) options.tooltip = {};
      options.tooltip.formatter = window['everviz'].tooltipFormatter;
    }


    if (options.yAxis && options.yAxis.length === 1) options.yAxis = options.yAxis[0];
    if (options.xAxis && options.xAxis.length === 1) options.xAxis = options.xAxis[0];
    if (options.zAxis && options.zAxis.length === 1) options.zAxis = options.zAxis[0];

    /*
// Sample of extending options:
Highcharts.merge(true, options, {
    chart: {
        backgroundColor: "#bada55"
    },
    plotOptions: {
        series: {
            cursor: "pointer",
            events: {
                click: function(event) {
                    alert(this.name + " clicked\n" +
                          "Alt: " + event.altKey + "\n" +
                          "Control: " + event.ctrlKey + "\n" +
                          "Shift: " + event.shiftKey + "\n");
                }
            }
        }
    }
});
*/
Highcharts.merge(true, options, { 
data: { 
dateFormat: "mm/dd/YYYY" 
} 
}); 



      if (options && (options.lang || options.global)) {
        Highcharts.setOptions({
          global: options.global || {},
          lang: options.lang || {}
        });
      }

      if (Highcharts.Annotation) {
        Highcharts.Annotation.ControlPoint.prototype.redraw = function (animation) {
          this.graphic[animation ? 'animate' : 'attr'](
              this.options.positioner ? this.options.positioner.call(this, this.target) : null
          );
        };
      }

      chartCreated = true;
      window.HighchartsCloud.hasLoaded = true; 
      setTimeout(function(){
          if (window["everviz"] && window["everviz"].pendingAnim) {
            //TODO: change to using classes instead.
            //Bit of work to do there due to backward compatibility
            const elements = document.querySelectorAll(
              '#' + elementClassName + 
              ', #' + legacyElementClassName
            );
            const elementsArray = Array.prototype.slice.call(elements);
            elementsArray.forEach(function(element, elementIndex) {

              window["everviz"].updateRenderTo(optionsStub, element);
              const stubbedChart = new Highcharts.StockChart(optionsStub);
              

              window["everviz"].pendingAnim({
                id: element.id + '-' + elementIndex, 
                loaded: false,
                options: options,
                appear:function(){
                  window.everviz.disconnectResizeObserver(stubbedChart);
                  window["everviz"].updateRenderTo(options, element);
                  new Highcharts.StockChart(options);

                },
                element: element
              });
            });

          } else {
            const element = document.querySelector('#' + legacyElementClassName);

            if (element) new Highcharts.StockChart(legacyElementClassName, options)
            else new Highcharts.StockChart(elementClassName, options) 

            
          }
      }, delayGen);
    }
  }

  function check(scripts, cb) {
    if (loaded === scripts.length) {
      if (cb) {
        cb();
      } else {


        //Create first project
        if (!window.HighchartsCloud.versions ||
           (window.HighchartsCloud.versions && window.HighchartsCloud.versions.length !== window.HighchartsCloud.ondone.length)) {
             
          for (var i = 0; i < window.HighchartsCloud.ondone.length; i++) {
            try {
              window.HighchartsCloud.ondone[i]();
            } catch(e) {
              console.error(e);
            }
          }
        } else {
          if (window.HighchartsCloud.stack.length) {
            window.HighchartsCloud.stack[0]();
            window.HighchartsCloud.stack.shift();
            const shouldRenderNextChart = window.HighchartsCloud.stack.length > 0;
            if (shouldRenderNextChart) {
              window.HighchartsCloud.stack[0](true);
            }
          }
        }
        
      }
    }
  }

  function loadScript(s, scripts, cb) {
    if (!s) next();
    
    function next() {
      ++loaded;
      if (loaded < scripts.length) {
        loadScript(scripts[loaded], scripts, cb);
      }
      check(scripts, cb);
    }

    if (isScriptAlreadyIncluded(s)) {
      return next();
    }

    var n = document.createElement('script');

    n.onload = function () {
      next();
    };

    if (s.indexOf('http') >= 0) {
      n.src = s;
    } else {
      n.src = cdn + s;
    }
    document.body.appendChild(n);
  }

  function loadExtraScripts(){
    if (extraScripts.length > 0) {
      loaded = 0;
      loadScript(extraScripts[0], extraScripts);
    } else {
      check(scripts);
    }
  }

  function loadExtraScriptsAndMakeChart(isUsingStack){
    loaded = 0;
    loadCSS();
    if (extraScripts.length > 0) {
      if (isUsingStack) {
        window.HighchartsCloud.stack[0] = createChart;
        loadScript(extraScripts[0], extraScripts);
      }
      else loadScript(extraScripts[0], extraScripts, createChart);
    } else {
      check(extraScripts);
    }
  }

  function getAllScripts(){
    var evervizScripts = [];
    var allScripts = scripts.map(function(script) {
      return 'highcharts/'+ script.replace('highcharts/highcharts.js', 'highcharts.js').replace('.js', '');
    }).concat(
      extraScripts.map(function(script) {
        if (script.indexOf('https://app.everviz.com/resources/highcharts/11.4.8/') > -1) {
          return 'highcharts/'+ script.replace('https://app.everviz.com/resources/highcharts/11.4.8/', '').replace('.js', '');
        } else if (script.indexOf('https://app.everviz.com/') > -1) {
          evervizScripts.push(script);
          return null;
        } else return script;
      }).filter(function(s) {
        return s !== null;
      })
    );

    allScripts.forEach(function(script) {
      if (window.HighchartsCloud.allScripts)
        window.HighchartsCloud.allScripts[script] = 1
    });

    return {
      allHighchartsScripts: allScripts,
      evervizScripts: evervizScripts
    }
  }

  function loadRequireJSScript(){
    require.config({
      packages: [{
        name: 'highcharts',
        main: 'highcharts'
      }],
      paths: {
        'highcharts': 'https://app.everviz.com/resources/highcharts/11.4.8'
      }
    });

    const allScripts = getAllScripts();

    require(
      allScripts.allHighchartsScripts,
      function (Highcharts) {
        //Attach highcharts to the window for use in the everviz scripts
        window.Highcharts = Highcharts;
        if (allScripts && allScripts.evervizScripts.length) {
          require(allScripts.evervizScripts, function(){
            createChart();
            loadCSS();
          })
        } else {
          createChart();
          loadCSS();
        }
      }
    );
  }

  function loadInitialScript(){
    if (window['require'] && typeof require === "function" && typeof require.specified === "function") {
      loadRequireJSScript();
    } else {
      getAllScripts()
      loadScript(scripts[0], scripts, loadExtraScripts);
      loadCSS();
    }
  }

  if (typeof window['HighchartsCloud'] === 'undefined') {
    window.HighchartsCloud = {
      ondone: [createChart],
      stack: [createChart],
      hasWrapped: false,
      hasLoaded: false,
      externalCSS: externalCSS,
      versions: [injectVersion],
      types: ['chart'],
      allScripts: {},
      projectUUIDs: {'YFsS4g98P': 1},
    };

    loadInitialScript();

  } else {
    if (window.HighchartsCloud.externalCSS) window.HighchartsCloud.externalCSS.push(externalCSS);
    if (!window.HighchartsCloud.hasLoaded) {
      if (!window.HighchartsCloud.projectUUIDs) window.HighchartsCloud.projectUUIDs = {};

      if (!window.HighchartsCloud.projectUUIDs['YFsS4g98P']) {

        window.HighchartsCloud.projectUUIDs['YFsS4g98P'] = 1;
        window.HighchartsCloud.ondone.push(loadExtraScriptsAndMakeChart);
        if (window.HighchartsCloud.stack) {
          window.HighchartsCloud.stack.push(loadExtraScriptsAndMakeChart);
          window.HighchartsCloud.versions.push(injectVersion);
          window.HighchartsCloud.types.push('chart');
        }

      }
      if (window['require'] && typeof require === "function" && typeof require.specified === "function") {
        getAllScripts()
        loadRequireJSScript();
      }
    }
    else {
      if (window['require'] && typeof require === "function" && typeof require.specified === "function") {
        loadRequireJSScript();
      } else {
        getAllScripts()
        loadExtraScriptsAndMakeChart();
      }
    }
  }

}());
