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

function onSearch(){
    const query = document.getElementById('song-search').value;
    const parent = document.getElementById('search-results');
    fetch(`/search?query=${query}`).then(res => res.json()).then(data => {
        console.log(data);
        const list = data['tracks']['items'];
        list.forEach((suggestion)=> {
            const textDiv = document.createElement('p');
            textDiv.innerText = suggestion['name'] + ' by ' + suggestion['artists'][0]['name'];
            parent.appendChild(textDiv);
        });
    });
}

function onSave(id) {
    fetch(`/save?id=${id}`).then(res=>res.json()).then(data => {
        //update it to be filled
        if (document.getElementById(`save-button-empty-${id}`).style.display !== "none"){
            document.getElementById(`save-button-empty-${id}`).style.display = "none";
        }else{
            document.getElementById(`save-button-empty-${id}`).style.display = "inline";
        }
        if (document.getElementById(`save-button-filled-${id}`).style.display !== "none"){
            document.getElementById(`save-button-filled-${id}`).style.display = "none";
        }else{
            document.getElementById(`save-button-filled-${id}`).style.display = "inline";
        }
    });
}

