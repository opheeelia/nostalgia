const urlParams = new URLSearchParams(location.search);

const season = urlParams.get('season');
const year = urlParams.get('year');

function setDefaultSelected(obj, val) {
    for (i=0;i<obj.options.length;i++){
        if (obj.options[i].value === val){
            obj.options[i].selected = true;
            break;
        }
    }
    return;
}

setDefaultSelected(document.getElementById('season'), season);
setDefaultSelected(document.getElementById('year'), year);
