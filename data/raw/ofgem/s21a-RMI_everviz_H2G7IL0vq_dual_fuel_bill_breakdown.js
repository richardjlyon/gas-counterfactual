(function () {
  //Inject code v5.2

  var highcharts = document.createElement('script');
  var injectVersion = 6;
  var cdn = 'https://app.everviz.com/resources/highcharts/11.4.8/';
  var loaded = 0;  
  var encodedUrl = encodeURI('https://https://app.everviz.com//show/H2G7IL0vq');
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

  var legacyElementClassName = 'highcharts-H2G7IL0vq';
  var elementClassName = 'everviz-H2G7IL0vq';
  var externalCSS = [
    "https://app.everviz.com/resources/css/highcharts-data-table.css"
  ];

  var extraScripts = [
  "https://app.everviz.com/resources/js/highcharts-scroll-animation.js",
  "https://app.everviz.com/resources/js/everviz-utils.js",
  "https://app.everviz.com/resources/js/highcharts-overrides.js",
  "https://app.everviz.com/resources/js/highcharts-resize.js",
  ];

  var options = {"chart":{"type":"column","polar":false,"height":511},"plotOptions":{"series":{"stacking":"normal","allowPointSelect":true,"states":{"select":{"color":"#EFFFEF","borderColor":"black","dashStyle":"dot"},"inactive":{"opacity":0.2}},"label":{"enabled":false},"marker":{"enabled":false},"lineWidth":3}},"yAxis":{"reversedStacks":true,"labels":{"format":"{value}"},"title":{"useHTML":true,"text":"GBP £s"}},"title":{"align":"left","x":10,"useHTML":true,"text":"Large legacy suppliers: Domestic dual fuel bill breakdown over time\n\n"},"subtitle":{"align":"left","x":10,"useHTML":true,"text":"\n"},"credits":{"href":"https://www.ofgem.gov.uk","position":{"x":-12,"y":-35},"style":{"fontSize":"14px"},"text":"Source: Ofgem analysis of companies’ Consolidated Segmental Statements"},"lang":{"shortMonths":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],"weekdays":["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"],"months":["January","February","March","April","May","June","July","August","September","October","November","December"],"numericSymbols":["k","M","G","T","P","E"]},"colors":["#e86e1e","#45286f","#e2c700","#cd1f45","#2363af","#51c1b5","#a1abb2","#9e712a","#0a4125","#a0b100","#000000","#9e712a","#51c1b5"],"legend":{"align":"center","verticalAlign":"bottom","itemMarginBottom":10,"x":0,"symbolRadius":2},"series":[{"turboThreshold":0,"type":"column","name":"% who are Detractors","data":[],"_colorIndex":0,"_symbolIndex":0},{"turboThreshold":0,"type":"column","name":"% who are Passive","data":[],"_colorIndex":1,"_symbolIndex":0},{"turboThreshold":0,"type":"column","name":"% who are Promoters","data":[],"_colorIndex":2,"_symbolIndex":0},{"turboThreshold":0,"type":"column","name":"Net Promoter Score","data":[],"_colorIndex":3,"_symbolIndex":0},{"data":[],"turboThreshold":0,"_colorIndex":4,"_symbolIndex":0,"type":"column"},{"data":[],"turboThreshold":0,"_colorIndex":5,"_symbolIndex":0,"type":"column"},{"data":[],"turboThreshold":0,"_colorIndex":6,"_symbolIndex":0,"type":"column"},{"data":[],"turboThreshold":0,"_colorIndex":7,"_symbolIndex":0,"type":"column"},{"data":[],"turboThreshold":0,"_colorIndex":8,"_symbolIndex":0,"type":"line","dashStyle":"ShortDot"}],"stockTools":{"gui":{"enabled":false}},"navigation":{"bindingsClassName":"tools-container","events":{}},"labels":{"items":[]},"pane":{"background":[]},"responsive":{"rules":[]},"exporting":{"scale":2,"url":"https://api.everviz.com/export"},"accessibility":{"description":"This chart is a breakdown of the prepayment price cap (GBP £)"},"caption":{"style":{"fontFamily":"Default","color":"#5c5656","fontSize":"14px","fontWeight":"normal","fontStyle":"normal","fill":"#666666","width":"1184px"},"align":"left","x":9,"y":1,"text":"Information correct as of: April 2024.","useHTML":true},"tooltip":{"valueSuffix":"","shared":false,"valuePrefix":"£"},"annotations":[],"data":{"csv":"\"null\";\"Wholesale costs\";\"Direct costs\";\"Network costs\";\"Environmental/social costs\";\"Other direct costs\";\"Operating costs\";\"EBIT\";\"VAT\";\"Bill\"\n2009;621;290;;;;132;8;52;1095\n2010;588;280;;;;160;35;53;1116\n2011;537;287;;;;152;30;50;1057\n2012;612;347;;;;161;53;59;1232\n2013;628;;276;109;0;163;49;61;1286\n2014;532;;278;100;5;166;51;57;1190\n2015;506;;279;86;7;182;49;55;1165\n2016;425;;292;91;13;193;54;53;1123\n2017;404;;284;108;14;205;49;53;1117\n2018;445;;281;134;16;217;33;56;1184\n2019;464;;279;153;18;216;-16;56;1171\n2020;410;;300;182;26;221;-11;56;1184","googleSpreadsheet":false,"liveData":false,"text":false,"assignDataFields":[{"labels":"A","values":"B"},{"labels":"A","values":"C"},{"labels":"A","values":"D"},{"labels":"A","values":"E"},{"labels":"A","values":"F"},{"labels":"A","values":"G"},{"labels":"A","values":"H"},{"labels":"A","values":"I"},{"labels":"A","values":"J"}],"seriesMapping":[{"x":0,"y":1,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":2,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":3,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":4,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":5,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":6,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":7,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":8,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9},{"x":0,"y":9,"null":0,"wholesale_costs":1,"direct_costs":2,"network_costs":3,"environmental_social_costs":4,"other_direct_costs":5,"operating_costs":6,"ebit":7,"vat":8,"bill":9}]}};
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
    if ('Chart' === 'Map') window["everviz"].modifyMapType(options);
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
              const stubbedChart = new Highcharts.Chart(optionsStub);
              

              window["everviz"].pendingAnim({
                id: element.id + '-' + elementIndex, 
                loaded: false,
                options: options,
                appear:function(){
                  window.everviz.disconnectResizeObserver(stubbedChart);
                  window["everviz"].updateRenderTo(options, element);
                  new Highcharts.Chart(options);

                },
                element: element
              });
            });

          } else {
            const element = document.querySelector('#' + legacyElementClassName);

            if (element) new Highcharts.Chart(legacyElementClassName, options)
            else new Highcharts.Chart(elementClassName, options) 

            
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
      projectUUIDs: {'H2G7IL0vq': 1},
    };

    loadInitialScript();

  } else {
    if (window.HighchartsCloud.externalCSS) window.HighchartsCloud.externalCSS.push(externalCSS);
    if (!window.HighchartsCloud.hasLoaded) {
      if (!window.HighchartsCloud.projectUUIDs) window.HighchartsCloud.projectUUIDs = {};

      if (!window.HighchartsCloud.projectUUIDs['H2G7IL0vq']) {

        window.HighchartsCloud.projectUUIDs['H2G7IL0vq'] = 1;
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
